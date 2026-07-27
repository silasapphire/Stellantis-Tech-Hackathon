"use client";

import { useEffect, useState } from "react";
import { collection, onSnapshot, orderBy, query, where, limit as fsLimit } from "firebase/firestore";
import { db } from "./firebase";
import type { Asset, AgentActivityEvent, Issue, Notification, SustainabilityPeriod, TelemetryReading } from "./types";

export function useAssets() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onSnapshot(collection(db, "assets"), (snapshot) => {
      setAssets(snapshot.docs.map((d) => ({ id: d.id, ...d.data() }) as Asset));
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  return { assets, loading };
}

export function useAsset(assetId: string) {
  const { assets } = useAssets();
  return assets.find((a) => a.id === assetId) ?? null;
}

export function useTelemetryHistory(assetId: string, points = 60) {
  const [readings, setReadings] = useState<TelemetryReading[]>([]);

  useEffect(() => {
    if (!assetId) return;
    const q = query(
      collection(db, "telemetry", assetId, "readings"),
      orderBy("timestamp", "desc"),
      fsLimit(points)
    );
    const unsubscribe = onSnapshot(q, (snapshot) => {
      const docs = snapshot.docs.map((d) => d.data() as TelemetryReading);
      setReadings(docs.reverse());
    });
    return unsubscribe;
  }, [assetId, points]);

  return readings;
}

export function useLatestReading(assetId: string) {
  const [reading, setReading] = useState<TelemetryReading | null>(null);

  useEffect(() => {
    if (!assetId) return;
    const q = query(collection(db, "telemetry", assetId, "readings"), orderBy("timestamp", "desc"), fsLimit(1));
    const unsubscribe = onSnapshot(q, (snapshot) => {
      setReading(snapshot.empty ? null : (snapshot.docs[0].data() as TelemetryReading));
    });
    return unsubscribe;
  }, [assetId]);

  return reading;
}

export function useIssues(assetId?: string) {
  const [issues, setIssues] = useState<Issue[]>([]);

  useEffect(() => {
    const base = collection(db, "issues");
    const q = assetId
      ? query(base, where("asset_id", "==", assetId), orderBy("detected_at", "desc"))
      : query(base, orderBy("detected_at", "desc"), fsLimit(100));
    const unsubscribe = onSnapshot(q, (snapshot) => {
      setIssues(snapshot.docs.map((d) => ({ id: d.id, ...d.data() }) as Issue));
    });
    return unsubscribe;
  }, [assetId]);

  return issues;
}

export function useNotifications(assetId?: string, take = 50) {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  useEffect(() => {
    const base = collection(db, "notifications");
    const q = assetId
      ? query(base, where("asset_id", "==", assetId), orderBy("created_at", "desc"), fsLimit(take))
      : query(base, orderBy("created_at", "desc"), fsLimit(take));
    const unsubscribe = onSnapshot(q, (snapshot) => {
      setNotifications(snapshot.docs.map((d) => ({ id: d.id, ...d.data() }) as Notification));
    });
    return unsubscribe;
  }, [assetId, take]);

  return notifications;
}

export function useAgentActivity(assetId?: string, take = 40) {
  const [events, setEvents] = useState<AgentActivityEvent[]>([]);

  useEffect(() => {
    const base = collection(db, "agent_activity");
    const q = assetId
      ? query(base, where("asset_id", "==", assetId), orderBy("timestamp", "desc"), fsLimit(take))
      : query(base, orderBy("timestamp", "desc"), fsLimit(take));
    const unsubscribe = onSnapshot(q, (snapshot) => {
      setEvents(snapshot.docs.map((d) => ({ id: d.id, ...d.data() }) as AgentActivityEvent));
    });
    return unsubscribe;
  }, [assetId, take]);

  return events;
}

export function useSustainability(assetId: string) {
  const [periods, setPeriods] = useState<SustainabilityPeriod[]>([]);

  useEffect(() => {
    if (!assetId) return;
    const q = query(
      collection(db, "sustainability", assetId, "periods"),
      orderBy("period_end", "desc"),
      fsLimit(30)
    );
    const unsubscribe = onSnapshot(q, (snapshot) => {
      setPeriods(snapshot.docs.map((d) => ({ id: d.id, ...d.data() }) as SustainabilityPeriod).reverse());
    });
    return unsubscribe;
  }, [assetId]);

  return periods;
}
