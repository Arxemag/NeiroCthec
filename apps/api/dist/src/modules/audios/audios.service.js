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
exports.AudiosService = void 0;
const common_1 = require("@nestjs/common");
const prisma_service_1 = require("../prisma/prisma.service");
const jobs_service_1 = require("../jobs/jobs.service");
function envInt(name, fallback) {
    const v = Number(process.env[name]);
    return Number.isFinite(v) ? v : fallback;
}
let AudiosService = class AudiosService {
    prisma;
    jobs;
    constructor(prisma, jobs) {
        this.prisma = prisma;
        this.jobs = jobs;
    }
    async listByProject(projectId, userId) {
        const project = await this.prisma.project.findUnique({ where: { id: projectId } });
        if (!project)
            throw new common_1.NotFoundException('Project not found');
        if (project.userId !== userId)
            throw new common_1.ForbiddenException();
        const audios = await this.prisma.audio.findMany({
            where: { projectId },
            orderBy: { createdAt: 'desc' },
        });
        return { project, audios };
    }
    async enqueueGeneration(projectId, userId) {
        const project = await this.prisma.project.findUnique({ where: { id: projectId } });
        if (!project)
            throw new common_1.NotFoundException('Project not found');
        if (project.userId !== userId)
            throw new common_1.ForbiddenException();
        const user = await this.prisma.user.findUnique({ where: { id: userId } });
        if (!user)
            throw new common_1.ForbiddenException();
        const maxChars = envInt('FREE_MAX_CHARS_PER_REQUEST', 6000);
        if (user.subscriptionStatus !== 'active' && project.text.length > maxChars) {
            throw new common_1.BadRequestException(`Text is too long for free plan (max ${maxChars} chars per request)`);
        }
        const maxPerDay = envInt('FREE_MAX_REQUESTS_PER_DAY', 5);
        if (user.subscriptionStatus !== 'active') {
            const since = new Date();
            since.setHours(0, 0, 0, 0);
            const countToday = await this.prisma.audio.count({
                where: { userId, createdAt: { gte: since } },
            });
            if (countToday >= maxPerDay)
                throw new common_1.BadRequestException('Daily free limit reached');
        }
        const audio = await this.prisma.audio.create({
            data: {
                projectId,
                userId,
                status: 'queued',
            },
        });
        await this.prisma.project.update({
            where: { id: projectId },
            data: { status: 'queued', errorMessage: null },
        });
        await this.jobs.enqueueGenerateAudio({ audioId: audio.id });
        return audio;
    }
    async getAudioForStream(audioId, userId) {
        const audio = await this.prisma.audio.findUnique({ where: { id: audioId } });
        if (!audio)
            throw new common_1.NotFoundException('Audio not found');
        if (audio.userId !== userId)
            throw new common_1.ForbiddenException();
        if (audio.status !== 'ready' || !audio.storageKey)
            throw new common_1.BadRequestException('Audio not ready');
        return audio;
    }
};
exports.AudiosService = AudiosService;
exports.AudiosService = AudiosService = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [prisma_service_1.PrismaService,
        jobs_service_1.JobsService])
], AudiosService);
//# sourceMappingURL=audios.service.js.map