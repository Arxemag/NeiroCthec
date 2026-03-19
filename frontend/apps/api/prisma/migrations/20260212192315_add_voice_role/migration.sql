-- CreateEnum
CREATE TYPE "VoiceRole" AS ENUM ('narrator', 'actor');

-- AlterTable
ALTER TABLE "Voice" ADD COLUMN     "role" "VoiceRole" NOT NULL DEFAULT 'actor';

-- CreateIndex
CREATE INDEX "Voice_role_idx" ON "Voice"("role");
