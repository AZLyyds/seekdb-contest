/*
 * Copyright (c) 2025 OceanBase.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef OCEANBASE_SHARE_INNER_TABLE_OB_INNER_TABLE_AI_COLUMN_CONSTANTS_H_
#define OCEANBASE_SHARE_INNER_TABLE_OB_INNER_TABLE_AI_COLUMN_CONSTANTS_H_

#include <stdint.h>

// Contest AI Column system tables. Keep in sync with
// ob_inner_table_schema_def.py (__all_ai_column / __all_ai_column_task).
//
// IMPORTANT: do NOT include the generated ob_inner_table_schema_constants.h
// here. That file is gitignored and may be absent depending on generate order;
// including it caused tip 5724f33 "执行失败" (compile). Use the same bare
// table names as other system tables (e.g. __all_ai_model).

#ifndef OB_ALL_AI_COLUMN_TID
const uint64_t OB_ALL_AI_COLUMN_TID = 1131;
#endif
#ifndef OB_ALL_AI_COLUMN_TASK_TID
const uint64_t OB_ALL_AI_COLUMN_TASK_TID = 1132;
#endif

// Prefer macros so a later include of generated constants (const char *const)
// can still compile if a TU sees both; service code only needs the names.
#ifndef OB_ALL_AI_COLUMN_TNAME
#define OB_ALL_AI_COLUMN_TNAME "__all_ai_column"
#endif
#ifndef OB_ALL_AI_COLUMN_TASK_TNAME
#define OB_ALL_AI_COLUMN_TASK_TNAME "__all_ai_column_task"
#endif

#endif /* OCEANBASE_SHARE_INNER_TABLE_OB_INNER_TABLE_AI_COLUMN_CONSTANTS_H_ */
