import type { ReactNode } from "react";

export function LoadingRows({ columns = 6 }: { columns?: number }) {
  return (
    <>
      {Array.from({ length: 6 }).map((_, rowIndex) => (
        <tr key={rowIndex}>
          {Array.from({ length: columns }).map((__, columnIndex) => (
            <td key={columnIndex}>
              <div className="skeleton h-4 w-full" />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

export function ErrorPanel({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Unknown error";
  return <div className="alert alert-error my-4 text-sm">{message}</div>;
}

export function EmptyRow({ columns, children = "No rows in selected range." }: { columns: number; children?: ReactNode }) {
  return (
    <tr>
      <td className="py-8 text-center text-base-content/50" colSpan={columns}>
        {children}
      </td>
    </tr>
  );
}
