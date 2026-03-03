import { Injectable, InternalServerErrorException, NotFoundException } from '@nestjs/common';
import { S3Client, GetObjectCommand, PutObjectCommand, HeadBucketCommand, CreateBucketCommand } from '@aws-sdk/client-s3';
import { Readable } from 'stream';

type RangeRequest = {
  start?: number;
  end?: number;
};

function requiredEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new InternalServerErrorException(`Missing env: ${name}`);
  return v;
}

@Injectable()
export class StorageService {
  private s3: S3Client;
  private bucket: string;

  constructor() {
    const endpoint = requiredEnv('S3_ENDPOINT');
    const region = requiredEnv('S3_REGION');
    const accessKeyId = requiredEnv('S3_ACCESS_KEY');
    const secretAccessKey = requiredEnv('S3_SECRET_KEY');
    this.bucket = requiredEnv('S3_BUCKET');

    this.s3 = new S3Client({
      region,
      endpoint,
      forcePathStyle: true,
      credentials: { accessKeyId, secretAccessKey },
    });
  }

  async ensureBucketExists() {
    try {
      await this.s3.send(new HeadBucketCommand({ Bucket: this.bucket }));
    } catch {
      // MinIO fresh install: bucket may not exist
      await this.s3.send(new CreateBucketCommand({ Bucket: this.bucket }));
    }
  }

  async putObject(params: { key: string; contentType: string; body: Buffer | Uint8Array }) {
    await this.ensureBucketExists();
    await this.s3.send(
      new PutObjectCommand({
        Bucket: this.bucket,
        Key: params.key,
        Body: params.body,
        ContentType: params.contentType,
      }),
    );
  }

  async getObjectStream(params: { key: string; range?: RangeRequest }) {
    await this.ensureBucketExists();
    const Range =
      params.range && (params.range.start !== undefined || params.range.end !== undefined)
        ? `bytes=${params.range.start ?? ''}-${params.range.end ?? ''}`
        : undefined;

    try {
      const out = await this.s3.send(
        new GetObjectCommand({
          Bucket: this.bucket,
          Key: params.key,
          Range,
        }),
      );

      // AWS SDK returns Body as stream (Readable in Node)
      const body = out.Body as Readable | undefined;
      if (!body) throw new NotFoundException('Audio not found');

      return {
        body,
        contentType: out.ContentType ?? 'application/octet-stream',
        contentLength: out.ContentLength,
        contentRange: out.ContentRange,
        acceptRanges: out.AcceptRanges,
      };
    } catch (e: any) {
      if (e?.$metadata?.httpStatusCode === 404) throw new NotFoundException('Audio not found');
      throw e;
    }
  }
}

