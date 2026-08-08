/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Workspace packages ship TypeScript source rather than a build step, so Next
  // must compile them as part of the app.
  transpilePackages: ["@faizy/ui", "@faizy/brand", "@faizy/db"],
  typedRoutes: true,
};

export default nextConfig;
