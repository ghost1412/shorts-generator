import crypto from 'crypto';

const ALGORITHM = 'aes-256-cbc';
const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY || 'shortsflow-placeholder-master-key-32chars'; // 32 characters
const IV_LENGTH = 16; 

function getEncryptionKey() {
  const key = process.env.ENCRYPTION_KEY || 'shortsflow-placeholder-master-key-32chars';
  const hashed = crypto.createHash('sha256').update(key).digest();
  
  // Internal diagnostic for dev terminal
  console.log(`[Crypto] Using Key Fingerprint: ${hashed.toString('hex').substring(0, 8)}`);
  
  return hashed;
}

export function encrypt(text: string) {
  if (!text) return '';
  
  // Prevent double-encryption: check for iv:hex pattern (hex has 32 chars for IV)
  const parts = text.split(':');
  if (parts.length === 2 && /^[0-9a-f]{32}$/.test(parts[0])) {
    return text;
  }

  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipheriv(ALGORITHM, getEncryptionKey(), iv);
  let encrypted = cipher.update(text);
  encrypted = Buffer.concat([encrypted, cipher.final()]);
  return iv.toString('hex') + ':' + encrypted.toString('hex');
}

export function decrypt(text: string) {
  if (!text || !text.includes(':')) return text;
  const textParts = text.split(':');
  const ivText = textParts.shift();
  if (!ivText) return text;
  const iv = Buffer.from(ivText, 'hex');
  const encryptedText = Buffer.from(textParts.join(':'), 'hex');
  const decipher = crypto.createDecipheriv(ALGORITHM, getEncryptionKey(), iv);
  let decrypted = decipher.update(encryptedText);
  decrypted = Buffer.concat([decrypted, decipher.final()]);
  return decrypted.toString();
}
