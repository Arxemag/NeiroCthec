"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.VoicesService = void 0;
const common_1 = require("@nestjs/common");
const prisma_service_1 = require("../prisma/prisma.service");
let VoicesService = class VoicesService {
    prisma;
    constructor(prisma) {
        this.prisma = prisma;
    }
    async list(filters) {
        return this.prisma.voice.findMany({
            where: {
                isActive: true,
                language: filters.language,
                gender: filters.gender,
                style: filters.style,
            },
            orderBy: [{ language: 'asc' }, { name: 'asc' }],
        });
    }
    async getById(id) {
        const v = await this.prisma.voice.findUnique({ where: { id } });
        if (!v || !v.isActive)
            throw new common_1.NotFoundException('Voice not found');
        return v;
    }
};
exports.VoicesService = VoicesService;
exports.VoicesService = VoicesService = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [prisma_service_1.PrismaService])
], VoicesService);
//# sourceMappingURL=voices.service.js.map