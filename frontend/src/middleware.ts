import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isProtectedRoute = createRouteMatcher(["/app(.*)"]);
const isDevAuth = process.env.NEXT_PUBLIC_DEV_AUTH === "true";

export default clerkMiddleware((auth, req) => {
  if (isDevAuth) {
    const path = req.nextUrl.pathname;
    const devToken = req.cookies.get("neco_dev_token")?.value;
    if (path.startsWith("/dev-login")) {
      return NextResponse.next();
    }
    if (path.startsWith("/app") && devToken) {
      return NextResponse.next();
    }
    // Dev mode: redirect to dev-login instead of Clerk when no token
    if (path.startsWith("/app") || path === "/") {
      return NextResponse.redirect(new URL("/dev-login", req.url));
    }
  }

  if (isProtectedRoute(req)) {
    auth().protect();
  }
});
export const config = {
  matcher: [
    "/((?!.+\\.[\\w]+$|_next).*)",
    "/",
    "/(api|trpc)(.*)",
  ],
};
