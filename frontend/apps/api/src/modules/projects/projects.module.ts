import { forwardRef, Module } from '@nestjs/common';
import { ProjectsController } from './projects.controller';
import { ProjectsService } from './projects.service';
import { BooksModule } from '../books/books.module';
import { UsersModule } from '../users/users.module';
import { VoicesModule } from '../voices/voices.module';

@Module({
  imports: [forwardRef(() => BooksModule), UsersModule, VoicesModule],
  controllers: [ProjectsController],
  providers: [ProjectsService],
  exports: [ProjectsService],
})
export class ProjectsModule {}

