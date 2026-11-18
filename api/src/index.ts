/** The composition root: the Worker over MotherDuck. */
import { createWorker } from "./worker";
import { motherDuck } from "./store";

export default createWorker(motherDuck);
