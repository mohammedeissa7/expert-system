import { Entity, PrimaryColumn, Column } from 'typeorm';

@Entity('dashboard_cache')
export class DashboardCache {
  @PrimaryColumn({ name: 'metric_key' })
  metricKey!: string;

  @Column({ type: 'jsonb', nullable: true })
  data!: unknown;

  @Column({ name: 'computed_at', type: 'timestamp', default: () => 'NOW()' })
  computedAt!: Date;
}
