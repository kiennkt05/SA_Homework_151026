const express = require('express');

const app = express();
app.disable('x-powered-by');
app.use(express.json({ limit: '100kb' }));

const port = Number(process.env.PORT || 3002);
const orders = [
  { id: 'o-1001', userId: '1', item: 'Mechanical keyboard', total: 1450000, status: 'PAID' },
  { id: 'o-1002', userId: '1', item: 'USB-C cable', total: 180000, status: 'SHIPPING' }
];

function requireGatewayIdentity(req, res, next) {
  const authenticatedUserId = req.get('x-auth-user-id');
  if (!authenticatedUserId) {
    return res.status(401).json({ error: 'Missing trusted gateway identity' });
  }
  req.authenticatedUserId = authenticatedUserId;
  return next();
}

app.get('/health', (_req, res) => res.json({ status: 'ok', service: 'orders' }));
app.use(requireGatewayIdentity);

app.get('/orders', (req, res) => {
  const userId = String(req.query.userId || req.authenticatedUserId);
  if (userId !== req.authenticatedUserId) {
    return res.status(403).json({ error: 'Cannot view another user orders' });
  }
  return res.json(orders.filter((order) => order.userId === userId));
});

app.post('/orders', (req, res) => {
  const order = {
    id: `o-${Date.now()}`,
    userId: req.authenticatedUserId,
    item: String(req.body.item || ''),
    total: Number(req.body.total || 0),
    status: 'CREATED'
  };
  if (!order.item || !Number.isFinite(order.total) || order.total <= 0) {
    return res.status(400).json({ error: 'item and a positive total are required' });
  }
  orders.push(order);
  return res.status(201).json(order);
});

app.listen(port, () => console.log(`Order service listening on ${port}`));

