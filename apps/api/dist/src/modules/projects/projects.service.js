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
exports.ProjectsService = void 0;
const common_1 = require("@nestjs/common");
const prisma_service_1 = require("../prisma/prisma.service");
let ProjectsService = class ProjectsService {
    prisma;
    constructor(prisma) {
        this.prisma = prisma;
    }
    async listByUser(userId) {
        return this.prisma.project.findMany({
            where: { userId },
            orderBy: { updatedAt: 'desc' },
            include: { audios: { orderBy: { createdAt: 'desc' }, take: 1 } },
        });
    }
    async getByIdForUser(projectId, userId) {
        const project = await this.prisma.project.findUnique({
            where: { id: projectId },
            include: { voices: { include: { voice: true } } },
        });
        if (!project)
            throw new common_1.NotFoundException('Project not found');
        if (project.userId !== userId)
            throw new common_1.ForbiddenException();
        return project;
    }
    async create(userId, data) {
        if (data.voiceIds.length === 0)
            throw new common_1.BadRequestException('At least one voice required');
        return this.prisma.project.create({
            data: {
                userId,
                title: data.title,
                text: data.text,
                language: data.language,
                voices: {
                    create: data.voiceIds.map((voiceId) => ({ voiceId })),
                },
            },
            include: { voices: true },
        });
    }
    async update(projectId, userId, patch) {
        const existing = await this.prisma.project.findUnique({ where: { id: projectId } });
        if (!existing)
            throw new common_1.NotFoundException('Project not found');
        if (existing.userId !== userId)
            throw new common_1.ForbiddenException();
        return this.prisma.$transaction(async (tx) => {
            if (patch.voiceIds) {
                await tx.projectVoice.deleteMany({ where: { projectId } });
                await tx.projectVoice.createMany({
                    data: patch.voiceIds.map((voiceId) => ({ projectId, voiceId })),
                    skipDuplicates: true,
                });
            }
            return tx.project.update({
                where: { id: projectId },
                data: {
                    title: patch.title,
                    text: patch.text,
                    language: patch.language,
                },
                include: { voices: { include: { voice: true } } },
            });
        });
    }
};
exports.ProjectsService = ProjectsService;
exports.ProjectsService = ProjectsService = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [prisma_service_1.PrismaService])
], ProjectsService);
//# sourceMappingURL=projects.service.js.map