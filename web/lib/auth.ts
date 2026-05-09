import { redirect } from "next/navigation";

import { serverApi } from "./server-api";
import type { UserOut } from "./types";

export async function requireUser() {
  try {
    return await serverApi<UserOut>("/auth/me");
  } catch (error) {
    const status = (error as Error & { status?: number }).status;
    if (status === 401) {
      redirect("/login");
    }
    throw error;
  }
}
