import { useEffect, useRef, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { useSimulationStore } from '@/stores/simulationStore';

interface SimTickEvent {
  tick: number;
  day: number;
  totalDays: number;
  metrics: {
    settledCount: number;
    queuedCount: number;
    failedCount: number;
    totalValueSettled: number;
  };
}

interface SimDayCompleteEvent {
  day: number;
  indicators: Record<string, number>;
  networkSnapshot: {
    nodeCount: number;
    edgeCount: number;
    avgDegree: number;
  };
}

interface SimCompleteEvent {
  simulationId: string;
  durationSeconds: number;
}

export function useSimulationSocket(simulationId: string | null) {
  const socketRef = useRef<Socket | null>(null);
  const { setStatus, addCompletedSimulation } = useSimulationStore();

  useEffect(() => {
    if (!simulationId) return;

    const socket = io('/', {
      path: '/socket.io',
      transports: ['websocket', 'polling'],
    });
    socketRef.current = socket;

    socket.on('sim:day_complete', (data: SimDayCompleteEvent) => {
      setStatus({
        simulationId,
        status: 'running',
        progressPct: (data.day / 30) * 100,
        currentDay: data.day,
        totalDays: 30,
      });
    });

    socket.on('sim:complete', (data: SimCompleteEvent) => {
      setStatus({
        simulationId,
        status: 'completed',
        progressPct: 100,
        currentDay: 30,
        totalDays: 30,
      });
      addCompletedSimulation(simulationId);
    });

    socket.on('sim:error', (data: { message: string }) => {
      setStatus({
        simulationId,
        status: 'failed',
        progressPct: 0,
        currentDay: 0,
        totalDays: 30,
        errorMessage: data.message,
      });
    });

    return () => {
      socket.disconnect();
    };
  }, [simulationId, setStatus, addCompletedSimulation]);

  const pause = useCallback(() => {
    socketRef.current?.emit('sim:pause', { simulation_id: simulationId });
  }, [simulationId]);

  const resume = useCallback(() => {
    socketRef.current?.emit('sim:resume', { simulation_id: simulationId });
  }, [simulationId]);

  const abort = useCallback(() => {
    socketRef.current?.emit('sim:abort', { simulation_id: simulationId });
  }, [simulationId]);

  return { pause, resume, abort };
}
