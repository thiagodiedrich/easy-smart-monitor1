/**
 * Rotas de Autenticação
 * 
 * Gerencia login e refresh tokens.
 * 
 * NOTA: Em produção, deve validar credenciais com banco de dados Python
 * ou serviço de autenticação separado. Esta é uma implementação básica.
 */
import { logger } from '../utils/logger.js';
import config from '../config.js';

export const authRoutes = async (fastify) => {
  /**
   * POST /api/v1/auth/login
   * 
   * Autentica usuário e retorna JWT tokens.
   * 
   * TODO: Integrar com banco de dados Python ou serviço de auth separado.
   */
  fastify.post('/login', {
    schema: {
      description: 'Autentica usuário',
      tags: ['Autenticação'],
      body: {
        type: 'object',
        required: ['username', 'password'],
        properties: {
          username: { type: 'string' },
          password: { type: 'string' },
        },
      },
    },
  }, async (request, reply) => {
    const { username, password } = request.body;
    
    // TODO: Validar credenciais com banco de dados Python
    // Por enquanto, validação básica
    // Em produção, fazer requisição HTTP para serviço Python ou consultar DB compartilhado
    if (!username || !password) {
      return reply.code(401).send({ 
        detail: 'Credenciais inválidas' 
      });
    }
    
    // Validação básica (remover em produção)
    // Em produção, validar com banco de dados Python
    const validUsers = process.env.VALID_USERS 
      ? JSON.parse(process.env.VALID_USERS)
      : { admin: 'admin123' }; // Default para desenvolvimento
    
    if (!validUsers[username] || validUsers[username] !== password) {
      logger.warn('Tentativa de login falhou', { username });
      return reply.code(401).send({ 
        detail: 'Credenciais inválidas' 
      });
    }
    
    // Gerar tokens
    const accessToken = fastify.jwt.sign(
      { sub: username, type: 'access' },
      { expiresIn: config.jwtExpiresIn }
    );
    
    const refreshToken = fastify.jwt.sign(
      { sub: username, type: 'refresh' },
      { expiresIn: '7d' }
    );
    
    logger.info('Login realizado com sucesso', { username });
    
    return {
      access_token: accessToken,
      refresh_token: refreshToken,
      token_type: 'bearer',
      expires_in: parseInt(config.jwtExpiresIn) * 60 || 900, // Converter minutos para segundos
    };
  });
  
  /**
   * POST /api/v1/auth/refresh
   * 
   * Renova access token usando refresh token.
   */
  fastify.post('/refresh', {
    schema: {
      description: 'Renova access token',
      tags: ['Autenticação'],
    },
  }, async (request, reply) => {
    try {
      const authHeader = request.headers.authorization;
      
      if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return reply.code(401).send({ 
          detail: 'Header Authorization ausente' 
        });
      }
      
      const token = authHeader.replace('Bearer ', '').trim();
      
      if (!token) {
        return reply.code(401).send({ 
          detail: 'Token não fornecido' 
        });
      }
      
      const decoded = fastify.jwt.verify(token);
      
      if (decoded.type !== 'refresh') {
        return reply.code(401).send({ 
          detail: 'Token não é do tipo refresh' 
        });
      }
      
      // Gerar novo access token
      const accessToken = fastify.jwt.sign(
        { sub: decoded.sub, type: 'access' },
        { expiresIn: config.jwtExpiresIn }
      );
      
      logger.info('Token renovado', { username: decoded.sub });
      
      return {
        access_token: accessToken,
        token_type: 'bearer',
        expires_in: parseInt(config.jwtExpiresIn) * 60 || 900,
      };
    } catch (error) {
      logger.warn('Erro ao renovar token', { error: error.message });
      return reply.code(401).send({ 
        detail: 'Token inválido ou expirado' 
      });
    }
  });
  
  /**
   * GET /api/v1/auth/me
   * 
   * Retorna informações do usuário autenticado.
   */
  fastify.get('/me', {
    schema: {
      description: 'Informações do usuário autenticado',
      tags: ['Autenticação'],
    },
  }, async (request, reply) => {
    try {
      await request.jwtVerify();
      
      return {
        username: request.user.sub,
        type: request.user.type,
      };
    } catch (error) {
      return reply.code(401).send({ 
        detail: 'Não autorizado' 
      });
    }
  });
};
