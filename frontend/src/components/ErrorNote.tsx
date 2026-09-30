interface ErrorNoteProps {
  title: string;
  children: React.ReactNode;
}

/** One error presentation for every page, so a failure never looks different
 *  depending on where it happened. */
export function ErrorNote({ title, children }: ErrorNoteProps) {
  return (
    <div className="system-note system-note-error" role="alert">
      <span className="system-note-signal" aria-hidden="true" />
      <strong>{title}</strong>
      <span>{children}</span>
    </div>
  );
}
