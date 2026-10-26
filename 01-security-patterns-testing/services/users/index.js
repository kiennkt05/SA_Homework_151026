const crypto = require('crypto');
const express = require('express');
const jwt = require('jsonwebtoken');
const { S3Client, PutObjectCommand } = require('@aws-sdk/client-s3');
const { getSignedUrl } = require('@aws-sdk/s3-request-presigner');

const app = express();
app.disable('x-powered-by');
app.use(express.json({ limit: '100kb' }));

const port = Number(process.env.PORT || 3001);
const jwtSecret = process.env.JWT_SECRET;
const bucket = process.env.MINIO_BUCKET || 'avatars';
const credentials = {
  accessKeyId: process.env.MINIO_ACCESS_KEY,
  secretAccessKey: process.env.MINIO_SECRET_KEY
};

if (!jwtSecret || !credentials.accessKeyId || !credentials.secretAccessKey) {
  throw new Error('JWT and MinIO credentials are required');
}

// The public endpoint is signed into the URL because the client uploads directly.
const publicS3 = new S3Client({
  region: 'us-east-1',
  endpoint: process.env.MINIO_PUBLIC_ENDPOINT || 'http://localhost:9000',
  forcePathStyle: true,
  credentials
});

const users = [
  {
    id: '1',
    email: 'admin@example.com',
    password: 'admin123',
    name: 'Nguyen Van An'
  }
];

function publicUser(user) {
  return { id: user.id, email: user.email, name: user.name };
}

function requireGatewayIdentity(req, res, next) {
  const authenticatedUserId = req.get('x-auth-user-id');
  if (!authenticatedUserId) {
    return res.status(401).json({ error: 'Missing trusted gateway identity' });
  }
  req.authenticatedUserId = authenticatedUserId;
  return next();
}

app.get('/health', (_req, res) => res.json({ status: 'ok', service: 'users' }));

app.post('/login', (req, res) => {
  const user = users.find(
    (candidate) => candidate.email === req.body.email && candidate.password === req.body.password
  );
  if (!user) return res.status(401).json({ error: 'Invalid credentials' });

  const token = jwt.sign(
    { email: user.email, name: user.name },
    jwtSecret,
    {
      algorithm: 'HS256',
      subject: user.id,
      issuer: 'security-patterns-homework',
      audience: 'api-gateway',
      expiresIn: '15m'
    }
  );
  return res.json({ token, tokenType: 'Bearer', expiresInSeconds: 900, user: publicUser(user) });
});

app.use(requireGatewayIdentity);

app.get('/users/:id', (req, res) => {
  if (req.params.id !== req.authenticatedUserId) {
    return res.status(403).json({ error: 'Cannot view another user' });
  }
  const user = users.find((candidate) => candidate.id === req.params.id);
  if (!user) return res.status(404).json({ error: 'User not found' });
  return res.json(publicUser(user));
});

app.post('/users/:id/avatar-upload-url', async (req, res) => {
  if (req.params.id !== req.authenticatedUserId) {
    return res.status(403).json({ error: 'Cannot upload an avatar for another user' });
  }

  const allowedTypes = new Set(['image/png', 'image/jpeg', 'image/webp']);
  const contentType = String(req.body.contentType || 'image/png');
  if (!allowedTypes.has(contentType)) {
    return res.status(400).json({ error: 'Only PNG, JPEG, or WebP is accepted' });
  }

  const extension = { 'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp' }[contentType];
  const objectKey = `users/${req.params.id}/${crypto.randomUUID()}.${extension}`;
  const command = new PutObjectCommand({ Bucket: bucket, Key: objectKey, ContentType: contentType });
  const uploadUrl = await getSignedUrl(publicS3, command, { expiresIn: 300 });

  return res.json({
    uploadUrl,
    method: 'PUT',
    requiredHeaders: { 'Content-Type': contentType },
    expiresInSeconds: 300,
    objectKey
  });
});

app.listen(port, () => console.log(`User service listening on ${port}`));

