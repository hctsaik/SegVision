# Tasks

Later change. Do not fold into `build-segvision-v1`. DINO stays off the v1 hot path.

- [x] 1. Author this change (proposal, design, DRP-R001–R004)
- [x] 2. Observational CPU spike: DINOv2-small prototypes from teacher mask → match on a moved image → SAM box
- [x] 3. Report overlays + IoU/F1 vs gold and vs ROI-copy MobileSAM; go/no-go for GUI wiring
- [x] 4. GUI/session wiring: default-off DINO prototype Fit-on-Accept and match-on-open, no ROI copy
