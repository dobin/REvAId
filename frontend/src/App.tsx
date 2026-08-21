import { ConfigProvider } from "@/config/ConfigProvider";
import { HealthPanel } from "@/components/HealthPanel";

export default function App() {
  return (
    <ConfigProvider fallback={<p style={{ padding: "1rem" }}>Loading configuration…</p>}>
      <HealthPanel />
    </ConfigProvider>
  );
}
