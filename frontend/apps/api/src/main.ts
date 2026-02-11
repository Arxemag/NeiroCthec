import { simpleRateLimit } from './middleware/rate-limit';
import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './modules/app.module';
import { ValidationPipe } from '@nestjs/common';
import cookieParser from 'cookie-parser';

async function bootstrap() {
  // 1. Создаём без cors:true
  const app = await NestFactory.create(AppModule);

  // 2. Включаем CORS вручную, с поддержкой cookies (localhost и 127.0.0.1 — разные origin)
  app.enableCors({
    origin: ['http://localhost:3000', 'http://127.0.0.1:3000'],
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
  await app.listen(port, "0.0.0.0");
}

bootstrap().catch((e) => {
  // eslint-disable-next-line no-console
  console.error(e);
  process.exit(1);
});

