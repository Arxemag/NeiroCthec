import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { PrismaModule } from './prisma/prisma.module';
import { AuthModule } from './auth/auth.module';
import { UsersModule } from './users/users.module';
import { VoicesModule } from './voices/voices.module';
import { ProjectsModule } from './projects/projects.module';
import { AudiosModule } from './audios/audios.module';
import { BooksModule } from './books/books.module';
import { SubscriptionModule } from './subscription/subscription.module';
import { HealthModule } from './health/health.module';
import { StorageModule } from './storage/storage.module';
import { JobsModule } from './jobs/jobs.module';
import { AdminModule } from './admin/admin.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    PrismaModule,
    StorageModule,
    JobsModule,
    AuthModule,
    UsersModule,
    VoicesModule,
    ProjectsModule,
    AudiosModule,
    BooksModule,
    SubscriptionModule,
    HealthModule,
    AdminModule,
  ],
})
export class AppModule {}

