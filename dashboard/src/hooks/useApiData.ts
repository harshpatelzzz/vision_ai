import { useQuery } from "@tanstack/react-query";
import * as api from "@/lib/api";

const REFRESH = 5000;

export const useHealth = () =>
  useQuery({ queryKey: ["health"], queryFn: api.getHealth, refetchInterval: REFRESH, retry: false });

export const useSecurityStatus = () =>
  useQuery({ queryKey: ["security"], queryFn: api.getSecurityStatus, refetchInterval: REFRESH });

export const useBlockchain = () =>
  useQuery({ queryKey: ["blockchain"], queryFn: api.getBlockchain, refetchInterval: REFRESH });

export const useBlockchainVerify = (enabled = false) =>
  useQuery({ queryKey: ["blockchain-verify"], queryFn: api.verifyBlockchain, enabled });

export const useMerkleRoot = () =>
  useQuery({ queryKey: ["merkle"], queryFn: api.getMerkleRoot, refetchInterval: REFRESH });

export const useNodes = () =>
  useQuery({ queryKey: ["nodes"], queryFn: api.getNodes, refetchInterval: REFRESH });

export const useHardwareStatus = () =>
  useQuery({ queryKey: ["hw-status"], queryFn: api.getHardwareStatus, refetchInterval: REFRESH });

export const useHardwareSensors = () =>
  useQuery({ queryKey: ["hw-sensors"], queryFn: api.getHardwareSensors, refetchInterval: 3000 });

export const useHardwareStream = () =>
  useQuery({ queryKey: ["hw-stream"], queryFn: api.getHardwareStream, refetchInterval: REFRESH });

export const useRfidStatus = () =>
  useQuery({ queryKey: ["rfid-status"], queryFn: api.getRfidStatus, refetchInterval: 3000 });

export const useRfidUsers = () =>
  useQuery({ queryKey: ["rfid-users"], queryFn: api.getRfidUsers, refetchInterval: REFRESH });

export const useRfidAccessLog = (limit = 100) =>
  useQuery({
    queryKey: ["rfid-log", limit],
    queryFn: () => api.getRfidAccessLog(limit),
    refetchInterval: 3000,
  });

export const useRfidLastScan = () =>
  useQuery({ queryKey: ["rfid-last"], queryFn: api.getRfidLastScan, refetchInterval: 2000 });

export const useAttestation = () =>
  useQuery({ queryKey: ["attestation"], queryFn: api.getAttestation, refetchInterval: 30000 });

export const useVpapVerify = (enabled = false) =>
  useQuery({ queryKey: ["vpap-verify"], queryFn: api.verifyVpap, enabled });
