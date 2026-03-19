-- CreateEnum
CREATE TYPE "RenderTaskStatus" AS ENUM ('queued', 'running', 'done', 'failed', 'cancelled');

-- CreateTable
CREATE TABLE "RenderTask" (
    "taskId" TEXT NOT NULL,
    "clientId" TEXT NOT NULL,
    "bookId" TEXT NOT NULL,
    "lineId" INTEGER NOT NULL,
    "engine" TEXT NOT NULL,
    "status" "RenderTaskStatus" NOT NULL DEFAULT 'queued',
    "storageKey" TEXT,
    "durationMs" INTEGER,
    "errorMessage" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "RenderTask_pkey" PRIMARY KEY ("taskId")
);

-- CreateIndex
CREATE INDEX "RenderTask_clientId_bookId_idx" ON "RenderTask"("clientId", "bookId");

-- CreateIndex
CREATE INDEX "RenderTask_status_idx" ON "RenderTask"("status");
