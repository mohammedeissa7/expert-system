import { Entity, PrimaryGeneratedColumn, Column } from 'typeorm';

@Entity('responses')
export class SurveyResponse {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ name: 'respondent_id', nullable: true, unique: true })
  respondentId!: number;

  @Column({ nullable: true })
  country!: string;

  @Column({ name: 'years_code_pro', nullable: true, type: 'int' })
  yearsCodePro!: number;

  @Column({ name: 'dev_type', type: 'text', array: true, nullable: true })
  devType!: string[];

  @Column({ name: 'languages_worked', type: 'text', array: true, nullable: true })
  languagesWorked!: string[];

  @Column({
    name: 'languages_wanted',
    type: 'text',
    array: true,
    nullable: true,
  })
  languagesWanted!: string[];

  @Column({
    name: 'devops_tools',
    type: 'text',
    array: true,
    nullable: true,
  })
  devopsTools!: string[];

  @Column({
    name: 'converted_comp_yearly',
    type: 'decimal',
    precision: 12,
    scale: 2,
    nullable: true,
  })
  convertedCompYearly!: number;

  @Column({ name: 'ed_level', nullable: true })
  edLevel!: string;

  @Column({ name: 'ai_tool_used', nullable: true })
  aiToolUsed!: boolean;

  @Column({ name: 'learn_code_online', nullable: true })
  learnCodeOnline!: boolean;

  @Column({ name: 'imported_at', type: 'timestamp', default: () => 'NOW()' })
  importedAt!: Date;
}
