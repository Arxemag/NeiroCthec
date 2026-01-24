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
exports.VoicesController = void 0;
const common_1 = require("@nestjs/common");
const voices_service_1 = require("./voices.service");
const guards_1 = require("../auth/guards");
const storage_service_1 = require("../storage/storage.service");
let VoicesController = class VoicesController {
    voices;
    storage;
    constructor(voices, storage) {
        this.voices = voices;
        this.storage = storage;
    }
    async list(language, gender, style) {
        const items = await this.voices.list({ language, gender, style });
        return {
            voices: items.map((v) => ({
                id: v.id,
                name: v.name,
                gender: v.gender,
                language: v.language,
                style: v.style,
                provider: v.provider,
                isActive: v.isActive,
                hasSample: Boolean(v.sampleStorageKey),
            })),
        };
    }
    async get(id) {
        const v = await this.voices.getById(id);
        return {
            voice: {
                id: v.id,
                name: v.name,
                gender: v.gender,
                language: v.language,
                style: v.style,
                provider: v.provider,
                isActive: v.isActive,
                hasSample: Boolean(v.sampleStorageKey),
            },
        };
    }
    async sample(id, res) {
        const v = await this.voices.getById(id);
        if (!v.sampleStorageKey) {
            res.status(404).json({ message: 'Sample not available' });
            return;
        }
        const obj = await this.storage.getObjectStream({ key: v.sampleStorageKey });
        res.setHeader('Content-Type', obj.contentType);
        if (obj.contentLength)
            res.setHeader('Content-Length', String(obj.contentLength));
        obj.body.pipe(res);
    }
};
exports.VoicesController = VoicesController;
__decorate([
    (0, common_1.UseGuards)(guards_1.AccessAuthGuard),
    (0, common_1.Get)(),
    __param(0, (0, common_1.Query)('language')),
    __param(1, (0, common_1.Query)('gender')),
    __param(2, (0, common_1.Query)('style')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, String, String]),
    __metadata("design:returntype", Promise)
], VoicesController.prototype, "list", null);
__decorate([
    (0, common_1.UseGuards)(guards_1.AccessAuthGuard),
    (0, common_1.Get)('/:id'),
    __param(0, (0, common_1.Param)('id')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String]),
    __metadata("design:returntype", Promise)
], VoicesController.prototype, "get", null);
__decorate([
    (0, common_1.UseGuards)(guards_1.AccessAuthGuard),
    (0, common_1.Get)('/:id/sample'),
    __param(0, (0, common_1.Param)('id')),
    __param(1, (0, common_1.Res)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object]),
    __metadata("design:returntype", Promise)
], VoicesController.prototype, "sample", null);
exports.VoicesController = VoicesController = __decorate([
    (0, common_1.Controller)('/api/voices'),
    __metadata("design:paramtypes", [voices_service_1.VoicesService,
        storage_service_1.StorageService])
], VoicesController);
//# sourceMappingURL=voices.controller.js.map