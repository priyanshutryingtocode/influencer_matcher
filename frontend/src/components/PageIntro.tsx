import type { ReactNode } from "react";

interface PageIntroProps {
  eyebrow: string;
  title: string;
  description: string;
  meta?: ReactNode;
}

export function PageIntro({ eyebrow, title, description, meta }: PageIntroProps) {
  return (
    <div className="page-intro">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="page-description">{description}</p>
      </div>
      {meta && <div className="page-intro-meta">{meta}</div>}
    </div>
  );
}
