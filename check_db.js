const { Pool } = require('pg');
require('dotenv').config();

const pool = new Pool({
  host: process.env.DB_HOST || '192.168.1.25',
  port: parseInt(process.env.DB_PORT || '5432'),
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME || 'wally_aura_web',
  ssl: false
});

async function main() {
  try {
    console.log('Consultando base de datos PostgreSQL...');
    const res = await pool.query('SELECT * FROM messages ORDER BY created_at DESC LIMIT 15');
    console.log('\n--- Tabla messages (últimos ' + res.rows.length + ') ---');
    for (const r of res.rows) {
      console.log(`[${r.created_at.toISOString()}] from_me: ${r.from_me} | jid: ${r.remote_jid} | phone: ${r.phone} | text: "${r.message_text}"`);
    }

    try {
      const inboxRes = await pool.query('SELECT * FROM agent_inbox ORDER BY created_at DESC LIMIT 10');
      console.log('\n--- Tabla agent_inbox (últimos ' + inboxRes.rows.length + ') ---');
      for (const r of inboxRes.rows) {
        console.log(`[${r.created_at.toISOString()}] processed: ${r.processed} | phone: ${r.phone} | text: "${r.message_text}"`);
      }
    } catch (e) {
      console.log('Tabla agent_inbox error o no existe:', e.message);
    }
  } catch (err) {
    console.error('Error:', err.message);
  } finally {
    await pool.end();
  }
}

main();
