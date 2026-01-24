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
exports.StorageService = void 0;
const common_1 = require("@nestjs/common");
const client_s3_1 = require("@aws-sdk/client-s3");
function requiredEnv(name) {
    const v = process.env[name];
    if (!v)
        throw new common_1.InternalServerErrorException(`Missing env: ${name}`);
    return v;
}
let StorageService = class StorageService {
    s3;
    bucket;
    constructor() {
        const endpoint = requiredEnv('S3_ENDPOINT');
        const region = requiredEnv('S3_REGION');
        const accessKeyId = requiredEnv('S3_ACCESS_KEY');
        const secretAccessKey = requiredEnv('S3_SECRET_KEY');
        this.bucket = requiredEnv('S3_BUCKET');
        this.s3 = new client_s3_1.S3Client({
            region,
            endpoint,
            forcePathStyle: true,
            credentials: { accessKeyId, secretAccessKey },
        });
    }
    async ensureBucketExists() {
        try {
            await this.s3.send(new client_s3_1.HeadBucketCommand({ Bucket: this.bucket }));
        }
        catch {
            // MinIO fresh install: bucket may not exist
            await this.s3.send(new client_s3_1.CreateBucketCommand({ Bucket: this.bucket }));
        }
    }
    async putObject(params) {
        await this.ensureBucketExists();
        await this.s3.send(new client_s3_1.PutObjectCommand({
            Bucket: this.bucket,
            Key: params.key,
            Body: params.body,
            ContentType: params.contentType,
        }));
    }
    async getObjectStream(params) {
        await this.ensureBucketExists();
        const Range = params.range && (params.range.start !== undefined || params.range.end !== undefined)
            ? `bytes=${params.range.start ?? ''}-${params.range.end ?? ''}`
            : undefined;
        try {
            const out = await this.s3.send(new client_s3_1.GetObjectCommand({
                Bucket: this.bucket,
                Key: params.key,
                Range,
            }));
            // AWS SDK returns Body as stream (Readable in Node)
            const body = out.Body;
            if (!body)
                throw new common_1.NotFoundException('Audio not found');
            return {
                body,
                contentType: out.ContentType ?? 'application/octet-stream',
                contentLength: out.ContentLength,
                contentRange: out.ContentRange,
                acceptRanges: out.AcceptRanges,
            };
        }
        catch (e) {
            if (e?.$metadata?.httpStatusCode === 404)
                throw new common_1.NotFoundException('Audio not found');
            throw e;
        }
    }
};
exports.StorageService = StorageService;
exports.StorageService = StorageService = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [])
], StorageService);
//# sourceMappingURL=storage.service.js.map