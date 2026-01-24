"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const rate_limit_1 = require("./middleware/rate-limit");
require("reflect-metadata");
const core_1 = require("@nestjs/core");
const app_module_1 = require("./modules/app.module");
const common_1 = require("@nestjs/common");
const cookie_parser_1 = __importDefault(require("cookie-parser"));
async function bootstrap() {
    // 1. Создаём без cors:true
    const app = await core_1.NestFactory.create(app_module_1.AppModule);
    // 2. Включаем CORS руками, с поддержкой cookies
    app.enableCors({
        origin: 'http://localhost:3000',
        credentials: true,
    });
    app.use((0, cookie_parser_1.default)());
    app.use((0, cookie_parser_1.default)());
    // MVP-rate-limit: auth endpoints and generation hotspots
    app.use('/api/auth', (0, rate_limit_1.simpleRateLimit)({
        windowMs: 60_000,
        max: 30,
    }));
    app.use('/api/projects', (0, rate_limit_1.simpleRateLimit)({
        windowMs: 60_000,
        max: 120,
    }));
    app.useGlobalPipes(new common_1.ValidationPipe({
        whitelist: true,
        forbidNonWhitelisted: true,
        transform: true,
    }));
    const port = Number(process.env.PORT ?? 4000);
    await app.listen(port);
}
bootstrap().catch((e) => {
    // eslint-disable-next-line no-console
    console.error(e);
    process.exit(1);
});
//# sourceMappingURL=main.js.map