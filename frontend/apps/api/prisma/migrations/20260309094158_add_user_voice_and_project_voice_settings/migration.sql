-- AlterTable
ALTER TABLE "Project" ADD COLUMN     "speakerSettings" JSONB;

-- CreateTable
CREATE TABLE "UserVoice" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "coreVoiceId" TEXT NOT NULL,
    "projectId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "UserVoice_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ProjectVoiceSettings" (
    "id" TEXT NOT NULL,
    "projectId" TEXT NOT NULL,
    "narratorVoiceId" TEXT,
    "maleVoiceId" TEXT,
    "femaleVoiceId" TEXT,

    CONSTRAINT "ProjectVoiceSettings_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "UserVoice_userId_idx" ON "UserVoice"("userId");

-- CreateIndex
CREATE INDEX "UserVoice_projectId_idx" ON "UserVoice"("projectId");

-- CreateIndex
CREATE UNIQUE INDEX "ProjectVoiceSettings_projectId_key" ON "ProjectVoiceSettings"("projectId");

-- CreateIndex
CREATE INDEX "ProjectVoiceSettings_projectId_idx" ON "ProjectVoiceSettings"("projectId");

-- AddForeignKey
ALTER TABLE "UserVoice" ADD CONSTRAINT "UserVoice_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "UserVoice" ADD CONSTRAINT "UserVoice_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ProjectVoiceSettings" ADD CONSTRAINT "ProjectVoiceSettings_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project"("id") ON DELETE CASCADE ON UPDATE CASCADE;
