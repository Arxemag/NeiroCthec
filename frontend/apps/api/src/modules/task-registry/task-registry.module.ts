import { Module } from '@nestjs/common';
import { TaskRegistryService } from './task-registry.service';
import { TaskRegistryController } from './task-registry.controller';

@Module({
  controllers: [TaskRegistryController],
  providers: [TaskRegistryService],
  exports: [TaskRegistryService],
})
export class TaskRegistryModule {}

