/**
 * SolarShare Frontend API Type Definitions
 * Matches FastAPI Pydantic Schemas in app/schemas/
 */

export interface DatasetMetrics {
  total_series: number;
  total_observations: number;
  total_profiles_computed: number;
  selected_profiles_count: number;
  is_real_data: boolean;
}

export interface SelectedProfileSummaryItem {
  cluster_id: number;
  series_name: string;
  mean_demand_kw: number;
  coefficient_of_variation: number;
  peak_to_average_ratio: number;
  cv?: number;
  par?: number;
}

export interface SolarMetrics {
  installed_capacity_kw: number;
  current_generation_kw: number;
  today_generation_kwh: number;
  performance_ratio: number;
}

export interface BatteryMetrics {
  capacity_kwh: number;
  current_soc_pct: number;
  stored_energy_kwh: number;
  status: string;
  power_kw: number;
}

export interface AllocationMetrics {
  active_tenants: number;
  total_estate_demand_kw: number;
  solar_coverage_pct: number;
  grid_dependency_pct: number;
  battery_contribution_pct: number;
}

export interface BillingMetrics {
  current_period: string;
  estimated_monthly_savings_inr: number;
  solar_tariff_inr_per_kwh: number;
  average_grid_tou_rate_inr_per_kwh: number;
}

export interface DashboardOverviewResponse {
  dataset_metrics: DatasetMetrics;
  solar_metrics: SolarMetrics;
  battery_metrics: BatteryMetrics;
  allocation_metrics: AllocationMetrics;
  billing_metrics: BillingMetrics;
  selected_profiles_summary: SelectedProfileSummaryItem[];
  is_demo: boolean;
  explanatory_note?: string;
}

export interface HourlyShape {
  hours: number[];
  values_kw: number[];
  normalized_values?: number[];
}

export interface LoadProfileRead {
  id: number;
  series_id: number;
  series_name?: string;
  methodology_version: string;
  mean_demand_kw: number;
  median_demand_kw: number;
  min_demand_kw: number;
  max_demand_kw: number;
  std_demand_kw: number;
  observation_count: number;
  coefficient_of_variation: number;
  peak_to_average_ratio: number;
  day_night_ratio: number;
  tou_peak_overlap_pct: number;
  weekday_weekend_ratio: number;
  cluster_id?: number;
  is_selected: boolean;
  distance_to_centroid?: number;
  selection_rationale?: string;
  weekday_shape?: HourlyShape | number[] | null;
  weekend_shape?: HourlyShape | number[] | null;
}

export interface LoadProfilesListResponse {
  profiles: LoadProfileRead[];
  total_count: number;
  selected_count: number;
  is_demo: boolean;
  explanatory_note?: string;
}

export interface PVConfigRead {
  id: number;
  estate_id: number;
  capacity_kw: number;
  efficiency: number;
  performance_ratio: number;
  effective_from: string;
  is_active: boolean;
  notes?: string;
  is_demo?: boolean;
  explanatory_note?: string;
}

export interface SolarGenerationRead {
  estate_id: number;
  timestamp_local: string;
  ghi_wm2: number;
  dni_wm2: number;
  dhi_wm2: number;
  cell_temperature_c: number;
  poa_irradiance_wm2: number;
  pv_power_kw: number;
  pv_energy_kwh: number;
  capacity_kw: number;
  performance_ratio: number;
}

export interface SolarGenerationListResponse {
  records: SolarGenerationRead[];
  total_records: number;
  is_demo: boolean;
  explanatory_note?: string;
}

export interface ForecastDataPoint {
  timestamp: string;
  predicted_value_kw: number;
  lower_bound_kw: number;
  upper_bound_kw: number;
}

export interface SolarForecastResponse {
  estate_id: number;
  forecast_period_hours: number;
  forecast_data: ForecastDataPoint[];
  total_generation_forecast_kwh: number;
  peak_generation_kw: number;
  is_demo: boolean;
  explanatory_note?: string;
  model_name?: string;
  training_record_count?: number;
  training_start_date?: string;
  training_end_date?: string;
  generated_at?: string;
}

export interface TenantForecastResponse {
  tenant_id: number;
  tenant_name: string;
  forecast_period_hours: number;
  forecast_data: ForecastDataPoint[];
  total_consumption_forecast_kwh: number;
  peak_demand_kw: number;
  is_demo: boolean;
  explanatory_note?: string;
}

export interface TenantAllocationItem {
  tenant_id: number;
  tenant_name: string;
  demanded_kw: number;
  allocated_solar_kw: number;
  battery_power_kw: number;
  grid_power_kw: number;
  fairness_share_pct: number;
}

export interface AllocationCurrentResponse {
  timestamp: string;
  total_solar_available_kw: number;
  total_estate_demand_kw: number;
  allocations: TenantAllocationItem[];
  unallocated_solar_kw: number;
  optimization_status: string;
  is_demo: boolean;
  explanatory_note?: string;
}

export interface BatteryConfigRead {
  id: number;
  estate_id: number;
  capacity_kwh: number;
  initial_soc_pct: number;
  min_soc_pct: number;
  max_soc_pct: number;
  max_charge_kw: number;
  max_discharge_kw: number;
  round_trip_efficiency: number;
  effective_from: string;
  is_active: boolean;
  notes?: string;
  is_demo?: boolean;
  explanatory_note?: string;
}

export interface BatteryStatusResponse {
  estate_id: number;
  current_soc_pct: number;
  current_stored_kwh: number;
  capacity_kwh: number;
  current_power_kw: number;
  operation_mode: string;
  health_soh_pct: number;
  is_demo: boolean;
  explanatory_note?: string;
}

export interface TariffPeriodRead {
  id: number;
  period_name: string;
  start_time: string;
  end_time: string;
  base_energy_charge_inr_per_kwh: number;
  electricity_tax_pct: number;
  effective_rate_inr_per_kwh: number;
}

export interface TariffRead {
  id: number;
  name: string;
  category: string;
  effective_from: string;
  source: string;
  source_reference: string;
  label: string;
  periods: TariffPeriodRead[];
  is_demo: boolean;
  explanatory_note?: string;
}

export interface BillingTenantSummary {
  tenant_id: number;
  tenant_name: string;
  total_consumption_kwh: number;
  solar_consumed_kwh: number;
  grid_consumed_kwh: number;
  solar_cost_inr: number;
  grid_cost_inr: number;
  total_bill_inr: number;
  savings_inr: number;
}

export interface BillingSummaryResponse {
  billing_period: string;
  total_estate_consumption_kwh: number;
  total_solar_consumed_kwh: number;
  total_grid_consumed_kwh: number;
  total_solar_cost_inr: number;
  total_grid_cost_inr: number;
  total_savings_inr: number;
  tenants: BillingTenantSummary[];
  is_demo: boolean;
  explanatory_note?: string;
}

export interface InvoiceLineRead {
  id: number;
  description: string;
  category: string;
  quantity_kwh: number;
  rate_inr_per_kwh: number;
  amount_inr: number;
}

export interface InvoiceRead {
  id: number;
  invoice_number: string;
  tenant_id: number;
  tenant_name?: string | null;
  billing_period: string;
  issue_date: string;
  due_date: string;
  status: string;
  total_consumption_kwh: number;
  solar_consumed_kwh: number;
  grid_consumed_kwh: number;
  solar_cost_inr: number;
  grid_cost_inr: number;
  total_bill_inr: number;
  savings_inr: number;
  line_items: InvoiceLineRead[];
  pdf_url?: string | null;
}

export interface InvoiceListResponse {
  billing_period: string;
  invoices: InvoiceRead[];
  count: number;
}

export interface AnalyticsOverviewResponse {
  total_public_series: number;
  total_observations: number;
  total_profiles_computed: number;
  selected_profiles_count: number;
  observation_date_range: {
    start: string;
    end: string;
  };
  selected_profiles_summary: SelectedProfileSummaryItem[];
  is_demo: boolean;
  explanatory_note?: string;
}

export interface HealthCheckResponse {
  status: string;
  app: string;
  environment: string;
  database: string;
}

export interface UserRead {
  id: number;
  email: string;
  role: 'ADMIN' | 'TENANT';
  tenant_id?: number | null;
  tenant_name?: string | null;
  source_client_series_id?: string | null;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface EstateRead {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  timezone: string;
  created_at?: string | null;
  updated_at?: string | null;
  weather_observation_count: number;
  solar_generation_estimate_count: number;
}

export interface EstatePreset {
  id: string;
  name: string;
  region: string;
  latitude: number;
  longitude: number;
  timezone: string;
  description: string;
}

export interface EstateUpdatePayload {
  name?: string;
  latitude?: number;
  longitude?: number;
  timezone?: string;
}

export interface EstateCreatePayload {
  name: string;
  latitude: number;
  longitude: number;
  timezone?: string;
}

export interface EstateSyncWeatherResponse {
  estate_id: number;
  latitude: number;
  longitude: number;
  start_date: string;
  end_date: string;
  records_written: number;
  generation_estimates_written: number;
  data_status: string;
  cache_hit: boolean;
  pv_config_id?: number | null;
  stale_rows_removed: number;
  message: string;
  hours_with_ghi: number;
  hours_missing_ghi: number;
  warning?: string | null;
}

