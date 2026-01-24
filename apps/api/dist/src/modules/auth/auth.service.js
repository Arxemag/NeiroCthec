"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AuthService = void 0;
const common_1 = require("@nestjs/common");
const prisma_service_1 = require("../prisma/prisma.service");
const argon2 = __importStar(require("argon2"));
const jwt_1 = require("@nestjs/jwt");
const nanoid_1 = require("nanoid");
function envNumber(name, fallback) {
    const v = Number(process.env[name]);
    return Number.isFinite(v) && v > 0 ? v : fallback;
}
let AuthService = class AuthService {
    prisma;
    jwt;
    constructor(prisma, jwt) {
        this.prisma = prisma;
        this.jwt = jwt;
    }
    async register(email, password) {
        const existing = await this.prisma.user.findUnique({ where: { email } });
        if (existing)
            throw new common_1.BadRequestException('Email already registered');
        const passwordHash = await argon2.hash(password);
        const user = await this.prisma.user.create({
            data: {
                email,
                passwordHash,
                subscription: { create: { status: 'free' } },
            },
        });
        return this.issueTokens(user.id);
    }
    async login(email, password) {
        const user = await this.prisma.user.findUnique({ where: { email } });
        if (!user)
            throw new common_1.UnauthorizedException('Invalid credentials');
        const ok = await argon2.verify(user.passwordHash, password);
        if (!ok)
            throw new common_1.UnauthorizedException('Invalid credentials');
        return this.issueTokens(user.id);
    }
    async logout(refreshTokenId) {
        await this.prisma.refreshToken.updateMany({
            where: { id: refreshTokenId },
            data: { revokedAt: new Date() },
        });
    }
    async rotateRefreshToken(userId, refreshTokenId) {
        const token = await this.prisma.refreshToken.findFirst({
            where: { id: refreshTokenId, userId },
        });
        if (!token || token.revokedAt)
            throw new common_1.ForbiddenException('Refresh token revoked');
        if (token.expiresAt.getTime() < Date.now())
            throw new common_1.ForbiddenException('Refresh token expired');
        await this.prisma.refreshToken.update({
            where: { id: refreshTokenId },
            data: { revokedAt: new Date() },
        });
        return this.issueTokens(userId);
    }
    async issueTokens(userId) {
        const user = await this.prisma.user.findUnique({ where: { id: userId } });
        if (!user)
            throw new common_1.UnauthorizedException();
        const accessTtl = envNumber('JWT_ACCESS_TTL_SECONDS', 900);
        const refreshTtl = envNumber('JWT_REFRESH_TTL_SECONDS', 30 * 24 * 3600);
        const accessPayload = {
            sub: user.id,
            email: user.email,
            role: user.role,
            subscriptionStatus: user.subscriptionStatus,
        };
        const refreshTokenId = (0, nanoid_1.nanoid)(24);
        const refreshPayload = { sub: user.id, tokenId: refreshTokenId };
        const accessToken = await this.jwt.signAsync(accessPayload, {
            secret: process.env.JWT_ACCESS_SECRET,
            expiresIn: accessTtl,
        });
        const refreshToken = await this.jwt.signAsync(refreshPayload, {
            secret: process.env.JWT_REFRESH_SECRET,
            expiresIn: refreshTtl,
        });
        // Store hashed refresh token id for revocation/auditing
        const tokenHash = await argon2.hash(refreshToken);
        await this.prisma.refreshToken.create({
            data: {
                id: refreshTokenId,
                userId: user.id,
                tokenHash,
                expiresAt: new Date(Date.now() + refreshTtl * 1000),
            },
        });
        return {
            user: {
                id: user.id,
                email: user.email,
                role: user.role,
                subscriptionStatus: user.subscriptionStatus,
            },
            accessToken,
            refreshToken,
            refreshTokenId,
            accessExpiresInSeconds: accessTtl,
            refreshExpiresInSeconds: refreshTtl,
        };
    }
};
exports.AuthService = AuthService;
exports.AuthService = AuthService = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [prisma_service_1.PrismaService,
        jwt_1.JwtService])
], AuthService);
//# sourceMappingURL=auth.service.js.map