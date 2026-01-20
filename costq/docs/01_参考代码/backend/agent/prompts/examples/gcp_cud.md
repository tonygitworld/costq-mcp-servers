### 示例 4: GCP CUD 分析（使用 GCP CUD 工具）

**用户**: "查询 CUD 利用率"

**系统自动注入账号上下文**:
```
用户查询: 查询 CUD 利用率

当前查询的 GCP 账号:
- 账号名称: cy-export
- GCP 项目 ID: cy-aiteam
- Billing Account ID: 015B75-932950-C931B5
```

**你的处理**:
1. ✅ 识别到这是 GCP 平台查询（账号上下文中包含 GCP 项目ID）
2. ✅ 识别到用户想查询 CUD（Committed Use Discounts）利用率
3. ✅ 使用 `gcp_cud_utilization` 工具
   - 不需要指定参数（系统会自动使用 billing_account_id="015B75-932950-C931B5"）
   - 查询整个组织的 CUD 利用率
4. ✅ 可选：使用其他 CUD 工具获取更多信息
   - `gcp_list_commitments`: 查看所有 CUD 承诺
   - `gcp_cud_coverage`: 查看 CUD 覆盖率
   - `gcp_cud_savings_analysis`: 查看节省金额

**示例响应**:
```
🔵 GCP CUD 利用率分析 - cy-export 组织

📊 查询范围: Billing Account 015B75-932950-C931B5 (整个组织)

### CUD 利用率概览
- 总承诺资源: 100 vCPU
- 已使用: 85 vCPU (85%)
- 未使用: 15 vCPU (15%)
- 利用率评级: ⚠️ 良好（建议提升到 90%+）

### 按项目分解
| 项目 | 承诺 | 使用 | 利用率 |
|------|------|------|--------|
| cy-aiteam | 60 vCPU | 55 vCPU | 92% ✅ |
| project-B | 40 vCPU | 30 vCPU | 75% ⚠️ |

### 💡 优化建议
1. project-B 的 CUD 利用率偏低（75%），建议检查资源使用情况
2. 整体利用率 85%，还有 15 vCPU 未充分利用（~$XXX/月浪费）
3. 考虑将未使用的 CUD 承诺转移到其他项目
```
