import { PageHeader } from "../components/PageHeader";

export function AboutPage() {
  return (
    <>
      <PageHeader
        eyebrow="About"
        title="Market-moving news, structured for verification"
        body="TickBase News 是 XAUUSD Event Radar 的公開出口，只展示已核准同步的 public-safe 事件摘要、分級、確認狀態與來源歸屬。"
      />
      <section className="mx-auto max-w-3xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="space-y-8">
          <section>
            <h2 className="text-xl font-semibold">系統定位</h2>
            <p className="mt-3 leading-7 text-base-content/70">
            本網站不是交易訊號服務。它的任務是把不同立場、不同速度、不同權力層級的消息來源整理成可追蹤的公開事件流，
            幫助讀者快速理解某個消息是否有官方確認、是否存在相反口徑，以及可能透過哪些公開敘事影響市場。
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold">事件分級</h2>
            <p className="mt-3 leading-7 text-base-content/70">
            Severity 反映事件在系統規則與模型流程中的相對重要性。`S` 與 `A` 表示更值得優先查看，
            但不表示任何交易方向，也不代表結果一定會影響金價。
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold">確認狀態</h2>
            <p className="mt-3 leading-7 text-base-content/70">
            `confirmed`、`partially confirmed`、`unconfirmed` 與 `contradicted`
            用於標示來源之間的確認程度。未確認事件應被視為待觀察，而不是事實結論。
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold">資料邊界</h2>
            <p className="mt-3 leading-7 text-base-content/70">
            公開網站不保存 HomeLab 內部 raw item 全文、AI prompt、token usage、私人通知記錄、Telegram session
            或任何內部管理資料。所有內容都經由 public sync 流程產生。
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold">免責聲明</h2>
            <p className="mt-3 leading-7 text-base-content/70">
            本網站內容僅供資訊與研究用途，不構成投資建議、交易建議、法律建議或財務建議。
            </p>
          </section>
        </div>
      </section>
    </>
  );
}
