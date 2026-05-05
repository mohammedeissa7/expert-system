import 'reflect-metadata';
import { DataSource } from 'typeorm';
import { SurveyResponse } from '../entities/SurveyResponse';
import { DashboardCache } from '../entities/DashboardCache';
import dotenv from 'dotenv';

dotenv.config();

export const AppDataSource = new DataSource({
  type: 'postgres',
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '5432'),
  username: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || 'postgres',
  database: process.env.DB_NAME || 'survey_db',
  synchronize: true,
  logging: process.env.NODE_ENV === 'development',
  entities: [SurveyResponse, DashboardCache],
  migrations: [],
  subscribers: [],
});
