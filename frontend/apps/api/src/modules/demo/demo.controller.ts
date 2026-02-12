import { BadRequestException, Controller, Get, Param, Post, Res, UploadedFile, UseInterceptors } from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import type { Response } from 'express';
import { DemoService } from './demo.service';

@Controller('/api/demo')
export class DemoController {
  constructor(private readonly demo: DemoService) {}

  @Post('/upload')
  @UseInterceptors(FileInterceptor('file'))
  upload(@UploadedFile() file?: Express.Multer.File) {
    if (!file) throw new BadRequestException('Файл не передан');
    const text = file.buffer.toString('utf-8').trim();
    if (!text) throw new BadRequestException('Пустой файл');

    const task = this.demo.createTask(file.originalname, text);
    return { task };
  }

  @Get('/tasks/:id')
  getTask(@Param('id') id: string) {
    return { task: this.demo.getTask(id) };
  }

  @Post('/tasks/:id/start-voice')
  async startVoice(@Param('id') id: string) {
    const task = await this.demo.startVoice(id);
    return { task };
  }

  @Get('/tasks/:taskId/chapters/:chapterId/stream')
  streamChapter(@Param('taskId') taskId: string, @Param('chapterId') chapterId: string, @Res() res: Response) {
    const wav = this.demo.getChapterAudio(taskId, chapterId);
    res.setHeader('Content-Type', 'audio/wav');
    res.setHeader('Content-Length', String(wav.length));
    res.status(200).send(wav);
  }
}
