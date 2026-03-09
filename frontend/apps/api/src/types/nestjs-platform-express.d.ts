declare module '@nestjs/platform-express' {
  export function FileInterceptor(
    fieldName: string,
    options?: { limits?: { fileSize?: number }; fileFilter?: (req: unknown, file: unknown, cb: (err: Error | null, accept: boolean) => void) => void }
  ): unknown;
}
