-- AlterTable
ALTER TABLE "RenderTask" ADD COLUMN     "emotion" JSONB,
ADD COLUMN     "isChapterHeader" BOOLEAN,
ADD COLUMN     "lineType" TEXT,
ADD COLUMN     "speaker" TEXT;
