import { useOutletContext } from "react-router-dom";
import type { OperatorOutletContext } from "./operator-context";

export const useOperatorOutlet = () => useOutletContext<OperatorOutletContext>();
