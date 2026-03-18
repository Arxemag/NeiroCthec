-- CreateEnum
CREATE TYPE "RenderAssemblyType" AS ENUM ('book_final_wav', 'book_chapter_wav');

-- CreateTable
CREATE TABLE "RenderAssembly" (
    "assemblyId" TEXT NOT NULL,
    "clientId" TEXT NOT NULL,
    "bookId" TEXT NOT NULL,
    "type" "RenderAssemblyType" NOT NULL,
    "chapterId" INTEGER NOT NULL DEFAULT 0,
    "storageKey" TEXT NOT NULL,
    "durationMs" INTEGER,
    "errorMessage" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "RenderAssembly_pkey" PRIMARY KEY ("assemblyId")
);

-- CreateIndex
CREATE INDEX "RenderAssembly_clientId_bookId_type_idx" ON "RenderAssembly"("clientId", "bookId", "type");

-- CreateIndex
CREATE UNIQUE INDEX "RenderAssembly_clientId_bookId_type_chapterId_key" ON "RenderAssembly"("clientId", "bookId", "type", "chapterId");
