/**
 * Utilitários de Autenticação
 * 
 * Valida usuários no banco de dados e diferencia entre device e frontend.
 */
import { queryDatabase } from './database.js';
import { logger } from './logger.js';
import bcrypt from 'bcrypt';

/**
 * Status do usuário
 */
export const UserStatus = {
  ACTIVE: 'active',
  INACTIVE: 'inactive',
  BLOCKED: 'blocked',
};

/**
 * Tipo de usuário
 */
export const UserType = {
  FRONTEND: 'frontend',
  DEVICE: 'device',
};

/**
 * Valida credenciais de usuário
 * 
 * @param {string} username - Nome de usuário
 * @param {string} password - Senha (plain text)
 * @param {string} userType - Tipo de usuário ('frontend' ou 'device')
 * @param {string} ipAddress - IP do cliente
 * @returns {Promise<Object|null>} Dados do usuário ou null se inválido
 */
export async function validateUserCredentials(username, password, userType, ipAddress, tenantId = null) {
  try {
    // Buscar usuário no banco
    const query = `
      SELECT 
        id,
        username,
        email,
        hashed_password,
        tenant_id,
        organization_id,
        workspace_id,
        role,
        user_type,
        status,
        failed_login_attempts,
        locked_until
      FROM users
      WHERE username = $1 AND user_type = $2
      ${tenantId ? 'AND tenant_id = $3' : ''}
    `;
    const params = tenantId ? [username, userType, tenantId] : [username, userType];
    const result = await queryDatabase(query, params);

    
    if (!result || result.length === 0) {
      logger.warn('Tentativa de login com usuário inexistente', {
        username,
        userType,
        ip: ipAddress,
      });
      // Não retornar erro específico para não vazar informações
      return null;
    }
    
    const user = result[0];
    
    // Verificar status (ANTES de verificar senha para evitar vazar informações)
    if (user.status === UserStatus.BLOCKED) {
      logger.warn('Tentativa de login com usuário bloqueado', {
        username,
        userType,
        ip: ipAddress,
      });
      // Não registrar como failed_login para não incrementar contador desnecessariamente
      return { error: 'BLOCKED', message: 'Usuário bloqueado. Contate o administrador.' };
    }
    
    if (user.status === UserStatus.INACTIVE) {
      logger.warn('Tentativa de login com usuário inativo', {
        username,
        userType,
        ip: ipAddress,
      });
      // Não registrar como failed_login
      return { error: 'INACTIVE', message: 'Usuário inativo. Contate o administrador.' };
    }
    
    // Verificar se está bloqueado temporariamente
    if (user.locked_until) {
      const lockedUntil = new Date(user.locked_until);
      if (lockedUntil > new Date()) {
        logger.warn('Tentativa de login com usuário temporariamente bloqueado', {
          username,
          userType,
          ip: ipAddress,
          locked_until: user.locked_until,
        });
        return { 
          error: 'LOCKED', 
          message: `Usuário bloqueado temporariamente até ${lockedUntil.toISOString()}` 
        };
      }
    }
    
    // Verificar senha
    const passwordValid = await bcrypt.compare(password, user.hashed_password);
    
    if (!passwordValid) {
      logger.warn('Tentativa de login com senha inválida', {
        username,
        userType,
        ip: ipAddress,
      });
      await recordFailedLogin(user.id);
      return null;
    }
    
    // Login bem-sucedido
    await recordSuccessfulLogin(user.id, ipAddress);
    
    return {
      id: user.id,
      username: user.username,
      email: user.email,
      tenant_id: user.tenant_id,
      organization_id: user.organization_id,
      workspace_id: user.workspace_id,
      role: user.role,
      user_type: user.user_type,
      status: user.status,
    };
    
  } catch (error) {
    logger.error('Erro ao validar credenciais', {
      error: error.message,
      username,
      userType,
    });
    return null;
  }
}

/**
 * Registra login bem-sucedido
 */
async function recordSuccessfulLogin(userId, ipAddress) {
  try {
    const query = `
      UPDATE users
      SET 
        last_login_at = NOW(),
        last_login_ip = $1,
        failed_login_attempts = 0,
        locked_until = NULL
      WHERE id = $2
    `;
    
    await queryDatabase(query, [ipAddress, userId]);
  } catch (error) {
    logger.error('Erro ao registrar login bem-sucedido', {
      error: error.message,
      userId,
    });
  }
}

/**
 * Registra tentativa de login falhada
 */
async function recordFailedLogin(userId) {
  try {
    // Incrementar contador e bloquear se necessário
    const query = `
      UPDATE users
      SET 
        failed_login_attempts = failed_login_attempts + 1,
        locked_until = CASE
          WHEN failed_login_attempts + 1 >= 5 THEN NOW() + INTERVAL '30 minutes'
          ELSE locked_until
        END
      WHERE id = $1
      RETURNING failed_login_attempts, locked_until
    `;
    
    const result = await queryDatabase(query, [userId]);
    
    if (result && result[0] && result[0].failed_login_attempts >= 5) {
      logger.warn('Usuário bloqueado após múltiplas tentativas falhadas', {
        userId,
        attempts: result[0].failed_login_attempts,
        locked_until: result[0].locked_until,
      });
    }
  } catch (error) {
    logger.error('Erro ao registrar login falhado', {
      error: error.message,
      userId,
    });
  }
}
