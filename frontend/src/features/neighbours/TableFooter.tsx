/**
 * Page-progress footer for a neighbour group. Rows stay virtualized; loading
 * more only fetches the next bounded API page.
 */
export function TableFooter({
  shown,
  total,
  onLoadMore,
  isLoadingMore = false,
}: {
  shown: number;
  total: number;
  onLoadMore?: () => void;
  isLoadingMore?: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        fontSize: "0.75rem",
        color: "#6b7280",
        padding: "0.25rem 0",
      }}
    >
      {shown < total && <span>showing {shown} of {total}</span>}
      {shown < total && onLoadMore && (
        <button type="button" onClick={onLoadMore} disabled={isLoadingMore}>
          {isLoadingMore ? "Loading…" : "Load more"}
        </button>
      )}
    </div>
  );
}
