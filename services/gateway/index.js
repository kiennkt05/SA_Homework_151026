const express = require('express');
const jwt = require('jsonwebtoken');
const { rateLimit } = require('express-rate-limit');

const app = express();
app.disable('x-powered-by');
app.use(express.json({ limit: '100kb' }));

const port = Number(process.env.PORT || 8080);
const jwtSecret = process.env.JWT_SECRET;
const userServiceUrl = process.env.USER_SERVICE_URL || 'http://users:3001';
const orderServiceUrl = process.env.ORDER_SERVICE_URL || 'http://orders:3002';

if (!jwtSecret) {
  throw new Error('JWT_SECRET is required');
}

const limiter = rateLimit({
  windowMs: 1000,
  limit: 10,
  standardHeaders: 'draft-7',
  legacyHeaders: false,
  message: { error: 'Too many requests; limit is 10 requests/second' }
});

function authenticate(req, res, next) {
  const authorization = req.get('authorization') || '';
  const [scheme, token] = authorization.split(' ');

  if (scheme !== 'Bearer' || !token) {
    return res.status(401).json({ error: 'Bearer token is required' });
  }

  try {
    req.auth = jwt.verify(token, jwtSecret, {
      algorithms: ['HS256'],
      issuer: 'security-patterns-homework',
      audience: 'api-gateway'
    });
    return next();
  } catch (_error) {
    return res.status(401).json({ error: 'Invalid or expired token' });
  }
}

async function fetchWithTimeout(url, options = {}, timeoutMs = 1500) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

async function relay(req, res, targetBaseUrl) {
  const targetUrl = new URL(req.originalUrl, targetBaseUrl);
  const headers = {
    accept: req.get('accept') || 'application/json',
    'x-auth-user-id': String(req.auth.sub),
    'x-auth-user-email': String(req.auth.email || '')
  };

  const options = { method: req.method, headers };
  if (!['GET', 'HEAD'].includes(req.method) && req.body !== undefined) {
    headers['content-type'] = 'application/json';
    options.body = JSON.stringify(req.body);
  }

  try {
    const upstream = await fetchWithTimeout(targetUrl, options);
    const contentType = upstream.headers.get('content-type');
    if (contentType) res.set('content-type', contentType);
    return res.status(upstream.status).send(Buffer.from(await upstream.arrayBuffer()));
  } catch (error) {
    const reason = error.name === 'AbortError' ? 'timeout' : 'unavailable';
    return res.status(502).json({ error: `Upstream service ${reason}` });
  }
}

app.get('/health', (_req, res) => res.json({ status: 'ok', service: 'gateway' }));

// Login is public; token verification is applied to every route below it.
app.post('/login', async (req, res) => {
  try {
    const upstream = await fetchWithTimeout(`${userServiceUrl}/login`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(req.body)
    });
    const contentType = upstream.headers.get('content-type');
    if (contentType) res.set('content-type', contentType);
    return res.status(upstream.status).send(Buffer.from(await upstream.arrayBuffer()));
  } catch (_error) {
    return res.status(502).json({ error: 'User service unavailable' });
  }
});

app.use(limiter);
app.use(authenticate);

// Routing: one public gateway address selects the correct internal service.
app.use('/users', (req, res) => relay(req, res, userServiceUrl));
app.use('/orders', (req, res) => relay(req, res, orderServiceUrl));

// Aggregation: call User and Order concurrently and return one response.
app.get('/dashboard', async (req, res) => {
  const userId = String(req.query.userId || req.auth.sub);
  if (userId !== String(req.auth.sub)) {
    return res.status(403).json({ error: 'Cannot view another user dashboard' });
  }

  const downstreamHeaders = { 'x-auth-user-id': String(req.auth.sub) };
  const [userResult, orderResult] = await Promise.allSettled([
    fetchWithTimeout(`${userServiceUrl}/users/${encodeURIComponent(userId)}`, { headers: downstreamHeaders }),
    fetchWithTimeout(`${orderServiceUrl}/orders?userId=${encodeURIComponent(userId)}`, { headers: downstreamHeaders })
  ]);

  async function parse(result) {
    if (result.status === 'rejected') return { ok: false, error: 'unavailable' };
    const response = result.value;
    if (!response.ok) return { ok: false, error: `HTTP ${response.status}` };
    return { ok: true, data: await response.json() };
  }

  const [user, orders] = await Promise.all([parse(userResult), parse(orderResult)]);
  const partial = !user.ok || !orders.ok;
  return res.status(partial ? 206 : 200).json({
    partial,
    user: user.ok ? user.data : null,
    orders: orders.ok ? orders.data : [],
    errors: {
      ...(user.ok ? {} : { user: user.error }),
      ...(orders.ok ? {} : { orders: orders.error })
    }
  });
});

app.use((_req, res) => res.status(404).json({ error: 'Route not found' }));

app.listen(port, () => console.log(`Gateway listening on ${port}`));

