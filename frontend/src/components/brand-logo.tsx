import Image from "next/image";

import { cn } from "@/lib/utils";

type BrandLogoProps = {
  className?: string;
  imageClassName?: string;
};

export function BrandLogo({ className, imageClassName }: BrandLogoProps) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-grid size-10 shrink-0 place-items-center overflow-hidden rounded-lg bg-primary text-primary-foreground",
        className,
      )}
    >
      <Image
        src="/brand/leadforge-icon.png"
        alt=""
        width={512}
        height={512}
        sizes="48px"
        className={cn("size-full object-cover", imageClassName)}
      />
    </span>
  );
}
