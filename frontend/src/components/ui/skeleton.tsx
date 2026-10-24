import * as React from "react";

import { cn } from "./utils";

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="skeleton" className={cn("skeleton rounded-md", className)} {...props} />;
}

export { Skeleton };
