-- AlterTable
ALTER TABLE "RenderTask" ADD COLUMN     "baseLineId" INTEGER,
ADD COLUMN     "isSegment" BOOLEAN,
ADD COLUMN     "segmentIndex" INTEGER,
ADD COLUMN     "segmentTotal" INTEGER;
