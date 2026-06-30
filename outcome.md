# Outcome: Raster Engineering Drawing → DXF

## Task
Convert the provided raster image of a metal engineering drawing into a layered DXF file
suitable for CAD review and downstream CNC / laser-cutting operations.

## Rubric (each criterion is graded pass / fail independently)

1. `/mnt/session/outputs/drawing.dxf` exists and is valid — `ezdxf.readfile()` completes without errors
2. At least one part outline exists as a closed LWPOLYLINE on the `CUT` layer
3. All clearly visible holes / apertures are represented as CIRCLE entities on the `CUT` layer
4. Bend / fold lines are present on the `BEND` layer **OR** `review.md` explicitly states "no bend lines detected"
5. `/mnt/session/outputs/review.md` exists with: entity count table, confidence level, and a list of ambiguities for the engineer to verify
