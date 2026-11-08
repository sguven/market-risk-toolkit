import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="max-w-md mx-auto text-center py-20">
      <div className="text-5xl font-semibold text-navy-200">404</div>
      <h1 className="text-lg font-semibold mt-2">Page not found</h1>
      <p className="text-sm text-muted mt-1">This topic, chapter or calculation does not exist (or is not authored yet).</p>
      <Link href="/" className="inline-block mt-5">
        <Button variant="outline">Back to dashboard</Button>
      </Link>
    </div>
  );
}
