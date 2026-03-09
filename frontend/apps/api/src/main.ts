import { simpleRateLimit } from './middleware/rate-limit';
import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './modules/app.module';
import { ValidationPipe } from '@nestjs/common';
import cookieParser from 'cookie-parser';

async function bootstrap() {
  // 1. Создаём без cors:true
  const app = await NestFactory.create(AppModule);

  // 2. CORS: в Docker браузер может открывать приложение по IP (например http://192.168.1.5:3000).
  // CORS_ORIGINS — список через запятую; если не задан — localhost. Регулярка для любого хоста: * (не для credentials).
  const corsOriginsEnv = process.env.CORS_ORIGINS?.trim();
  const corsOrigin = corsOriginsEnv
    ? corsOriginsEnv.split(',').map((o) => o.trim()).filter(Boolean)
    : ['http://localhost:3000', 'http://127.0.0.1:3000'];
  const corsOriginRegex = process.env.CORS_ORIGIN_REGEX?.trim();
  app.enableCors({
    origin: corsOriginRegex ? new RegExp(corsOriginRegex) : corsOrigin,
    credentials: true,
  });

  app.use(cookieParser());
  // MVP-rate-limit: auth endpoints and generation hotspots
  app.use(
    '/api/auth',
    simpleRateLimit({
      windowMs: 60_000,
      max: 30,
    }),
  );
  app.use(
    '/api/projects',
    simpleRateLimit({
      windowMs: 60_000,
      max: 120,
    }),
  );
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  const port = Number(process.env.PORT ?? 4000);
  // В Docker запросы идут с других контейнеров (web → api:4000). Слушать нужно 0.0.0.0, иначе ECONNREFUSED.
  const host = process.env.HOST ?? '0.0.0.0';
  await app.listen(port, host);
}

bootstrap().catch((e) => {
  // eslint-disable-next-line no-console
  console.error(e);
  process.exit(1);
});

