const { BufferJSON, initAuthCreds, proto } = require('@whiskeysockets/baileys');

/**
 * PostgreSQL Auth State Adapter for Baileys
 * Persists all WhatsApp credentials and cryptographic keys directly into PostgreSQL.
 * Eliminates the need for Docker persistent volume mounts.
 */
async function usePostgresAuthState(pool, sessionId = 'default') {
  // 1. Ensure the session_auth table exists
  await pool.query(`
    CREATE TABLE IF NOT EXISTS session_auth (
      session_id VARCHAR(64) NOT NULL,
      key_id VARCHAR(255) NOT NULL,
      data JSONB NOT NULL,
      updated_at TIMESTAMPTZ DEFAULT NOW(),
      PRIMARY KEY (session_id, key_id)
    );
  `);

  // Helper to read data by keyId
  const readData = async (keyId) => {
    try {
      const res = await pool.query(
        'SELECT data FROM session_auth WHERE session_id = $1 AND key_id = $2',
        [sessionId, keyId]
      );
      if (res.rows.length === 0) return null;
      return JSON.parse(JSON.stringify(res.rows[0].data), BufferJSON.reviver);
    } catch (err) {
      console.error(`[PgAuth] Error reading key ${keyId}:`, err.message);
      return null;
    }
  };

  // Helper to write data by keyId
  const writeData = async (keyId, value) => {
    try {
      if (value === null || value === undefined) {
        await pool.query(
          'DELETE FROM session_auth WHERE session_id = $1 AND key_id = $2',
          [sessionId, keyId]
        );
      } else {
        const serialized = JSON.parse(JSON.stringify(value, BufferJSON.replacer));
        await pool.query(
          `INSERT INTO session_auth (session_id, key_id, data, updated_at)
           VALUES ($1, $2, $3, NOW())
           ON CONFLICT (session_id, key_id)
           DO UPDATE SET data = EXCLUDED.data, updated_at = NOW();`,
          [sessionId, keyId, serialized]
        );
      }
    } catch (err) {
      console.error(`[PgAuth] Error writing key ${keyId}:`, err.message);
    }
  };

  // Helper to clear all session auth data on logout
  const clearSession = async () => {
    try {
      await pool.query('DELETE FROM session_auth WHERE session_id = $1', [sessionId]);
      console.log(`[PgAuth] ✅ Sesión "${sessionId}" eliminada de PostgreSQL.`);
    } catch (err) {
      console.error('[PgAuth] Error clearing session from DB:', err.message);
    }
  };

  // 2. Load or initialize credentials
  const existingCreds = await readData('creds');
  const creds = existingCreds || initAuthCreds();

  return {
    state: {
      creds,
      keys: {
        get: async (type, ids) => {
          const data = {};
          await Promise.all(
            ids.map(async (id) => {
              let value = await readData(`${type}-${id}`);
              if (type === 'app-state-sync-key' && value) {
                value = proto.Message.AppStateSyncKeyData.fromObject(value);
              }
              data[id] = value;
            })
          );
          return data;
        },
        set: async (data) => {
          const tasks = [];
          for (const category in data) {
            for (const id in data[category]) {
              const value = data[category][id];
              const key = `${category}-${id}`;
              tasks.push(writeData(key, value));
            }
          }
          await Promise.all(tasks);
        }
      }
    },
    saveCreds: () => writeData('creds', creds),
    clearSession
  };
}

module.exports = { usePostgresAuthState };
