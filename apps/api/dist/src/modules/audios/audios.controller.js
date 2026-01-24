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
var __param = (this && this.__param) || function (paramIndex, decorator) {
    return function (target, key) { decorator(target, key, paramIndex); }
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AudiosController = void 0;
const common_1 = require("@nestjs/common");
const guards_1 = require("../auth/guards");
const audios_service_1 = require("./audios.service");
const storage_service_1 = require("../storage/storage.service");
function parseRange(rangeHeader) {
    if (!rangeHeader || Array.isArray(rangeHeader))
        return undefined;
    const m = /^bytes=(\d*)-(\d*)$/.exec(rangeHeader);
    if (!m)
        return undefined;
    const start = m[1] ? Number(m[1]) : undefined;
    const end = m[2] ? Number(m[2]) : undefined;
    return { start, end };
}
let AudiosController = class AudiosController {
    audios;
    storage;
    constructor(audios, storage) {
        this.audios = audios;
        this.storage = storage;
    }
    async generate(req, projectId) {
        const audio = await this.audios.enqueueGeneration(projectId, req.user.sub);
        return { audio };
    }
    async list(req, projectId) {
        const { audios } = await this.audios.listByProject(projectId, req.user.sub);
        return {
            audios: audios.map((a) => ({
                id: a.id,
                status: a.status,
                format: a.format,
                durationSeconds: a.durationSeconds,
                createdAt: a.createdAt,
            })),
        };
    }
    async stream(req, res, audioId) {
        const audio = await this.audios.getAudioForStream(audioId, req.user.sub);
        const range = parseRange(req.headers['range']);
        const obj = await this.storage.getObjectStream({ key: audio.storageKey, range });
        res.setHeader('Content-Type', obj.contentType);
        res.setHeader('Accept-Ranges', obj.acceptRanges ?? 'bytes');
        if (obj.contentRange)
            res.setHeader('Content-Range', obj.contentRange);
        if (obj.contentLength)
            res.setHeader('Content-Length', String(obj.contentLength));
        // If range was requested, S3 returns 206
        if (range)
            res.status(206);
        obj.body.pipe(res);
    }
};
exports.AudiosController = AudiosController;
__decorate([
    (0, common_1.UseGuards)(guards_1.AccessAuthGuard),
    (0, common_1.Post)('/projects/:id/generate-audio'),
    __param(0, (0, common_1.Req)()),
    __param(1, (0, common_1.Param)('id')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object, String]),
    __metadata("design:returntype", Promise)
], AudiosController.prototype, "generate", null);
__decorate([
    (0, common_1.UseGuards)(guards_1.AccessAuthGuard),
    (0, common_1.Get)('/projects/:id/audios'),
    __param(0, (0, common_1.Req)()),
    __param(1, (0, common_1.Param)('id')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object, String]),
    __metadata("design:returntype", Promise)
], AudiosController.prototype, "list", null);
__decorate([
    (0, common_1.UseGuards)(guards_1.AccessAuthGuard),
    (0, common_1.Get)('/audios/:id/stream'),
    __param(0, (0, common_1.Req)()),
    __param(1, (0, common_1.Res)()),
    __param(2, (0, common_1.Param)('id')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object, Object, String]),
    __metadata("design:returntype", Promise)
], AudiosController.prototype, "stream", null);
exports.AudiosController = AudiosController = __decorate([
    (0, common_1.Controller)('/api'),
    __metadata("design:paramtypes", [audios_service_1.AudiosService,
        storage_service_1.StorageService])
], AudiosController);
//# sourceMappingURL=audios.controller.js.map