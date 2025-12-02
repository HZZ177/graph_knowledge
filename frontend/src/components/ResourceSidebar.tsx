import React, { useMemo } from 'react'
import { Typography, Badge, Input, Spin } from 'antd'
import {
  SearchOutlined,
  FolderOutlined,
  FolderOpenOutlined,
  RightOutlined,
  DownOutlined,
  FileOutlined,
} from '@ant-design/icons'

interface GroupCount {
  value: string | null
  count: number
}

interface SystemTypeCount {
  system: string | null
  type: string | null
  count: number
}

export interface SidebarGroup {
  key: string
  label: string
  count: number
  children?: SidebarGroup[]
}

interface ResourceSidebarProps {
  title: string
  groups: SidebarGroup[]
  selectedKey: string | null
  expandedKeys: string[]
  onSelect: (key: string | null) => void
  onExpand: (keys: string[]) => void
  loading?: boolean
  searchValue?: string
  onSearchChange?: (value: string) => void
  totalCount: number
}

/**
 * 将分组统计数据转换为侧边栏分组结构（单层）
 */
export function buildSingleLevelGroups(
  groups: GroupCount[],
  labelMap?: Record<string, string>,
): SidebarGroup[] {
  return groups.map((g) => ({
    key: g.value ?? '',
    label: labelMap?.[g.value ?? ''] ?? g.value ?? '其他',
    count: g.count,
  }))
}

/**
 * 将分组统计数据转换为侧边栏分组结构（两层：系统 -> 类型）
 */
export function buildTwoLevelGroups(
  bySystem: GroupCount[],
  byType: GroupCount[],
  systemLabelMap?: Record<string, string>,
  typeLabelMap?: Record<string, string>,
  bySystemType?: SystemTypeCount[],
): SidebarGroup[] {
  // 构建 system+type -> count 的映射表
  const systemTypeCountMap = new Map<string, number>()
  if (bySystemType) {
    for (const item of bySystemType) {
      const key = `${item.system ?? ''}::${item.type ?? ''}`
      systemTypeCountMap.set(key, item.count)
    }
  }

  // 系统作为一级分组
  return bySystem.map((sys) => ({
    key: sys.value ?? '',
    label: systemLabelMap?.[sys.value ?? ''] ?? sys.value ?? '其他',
    count: sys.count,
    // 类型作为二级分组，使用联合统计数据获取正确的数量
    children: byType.map((t) => {
      const mapKey = `${sys.value ?? ''}::${t.value ?? ''}`
      // 如果有联合统计数据，使用它；否则回退到 0
      const count = systemTypeCountMap.get(mapKey) ?? 0
      return {
        key: mapKey,
        label: typeLabelMap?.[t.value ?? ''] ?? t.value ?? '其他',
        count,
      }
    }).filter((child) => child.count > 0), // 只显示有数据的类型
  }))
}

const ResourceSidebar: React.FC<ResourceSidebarProps> = ({
  title,
  groups,
  selectedKey,
  expandedKeys,
  onSelect,
  onExpand,
  loading = false,
  searchValue,
  onSearchChange,
  totalCount,
}) => {
  const handleToggleExpand = (key: string) => {
    if (expandedKeys.includes(key)) {
      onExpand(expandedKeys.filter((k) => k !== key))
    } else {
      onExpand([...expandedKeys, key])
    }
  }

  const isAllSelected = selectedKey === null

  return (
    <div
      style={{
        width: 220,
        minWidth: 220,
        borderRight: '1px solid #f0f0f0',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: '#fafafa',
      }}
    >
      {/* 标题 */}
      <div style={{ padding: '12px 12px 8px', borderBottom: '1px solid #f0f0f0' }}>
        <Typography.Text strong style={{ fontSize: 13 }}>
          {title}
        </Typography.Text>
      </div>

      {/* 搜索框 */}
      {onSearchChange && (
        <div style={{ padding: '8px 12px' }}>
          <Input
            size="small"
            placeholder="搜索..."
            prefix={<SearchOutlined style={{ color: '#9ca3af' }} />}
            value={searchValue}
            onChange={(e) => onSearchChange(e.target.value)}
            allowClear
          />
        </div>
      )}

      {/* 分组列表 */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 20 }}>
            <Spin size="small" />
          </div>
        ) : (
          <>
            {/* 全部选项 */}
            <div
              onClick={() => onSelect(null)}
              style={{
                padding: '6px 12px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: isAllSelected ? '#e6f4ff' : 'transparent',
                borderLeft: isAllSelected ? '3px solid #1890ff' : '3px solid transparent',
              }}
            >
              <span style={{ fontSize: 13, fontWeight: isAllSelected ? 600 : 400 }}>全部</span>
              <Badge
                count={totalCount}
                style={{
                  backgroundColor: isAllSelected ? '#1890ff' : '#8c8c8c',
                  fontSize: 11,
                }}
                overflowCount={999}
                showZero
              />
            </div>

            {/* 分组项 */}
            {groups.map((group) => {
              const hasChildren = group.children && group.children.length > 0
              const isExpanded = expandedKeys.includes(group.key)
              const isSelected = selectedKey === group.key

              return (
                <div key={group.key}>
                  {/* 一级分组 */}
                  <div
                    style={{
                      padding: '6px 12px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      background: isSelected ? '#e6f4ff' : 'transparent',
                      borderLeft: isSelected ? '3px solid #1890ff' : '3px solid transparent',
                    }}
                  >
                    <div
                      style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0 }}
                      onClick={() => {
                        if (hasChildren) {
                          handleToggleExpand(group.key)
                        }
                        onSelect(group.key)
                      }}
                    >
                      {hasChildren ? (
                        <>
                          <span style={{ marginRight: 4, fontSize: 10, color: '#8c8c8c', flexShrink: 0 }}>
                            {isExpanded ? <DownOutlined /> : <RightOutlined />}
                          </span>
                          <span style={{ marginRight: 6, fontSize: 14, color: isExpanded ? '#faad14' : '#8c8c8c', flexShrink: 0 }}>
                            {isExpanded ? <FolderOpenOutlined /> : <FolderOutlined />}
                          </span>
                        </>
                      ) : (
                        <span style={{ marginRight: 6, fontSize: 14, color: '#8c8c8c', flexShrink: 0 }}>
                          <FolderOutlined />
                        </span>
                      )}
                      <span
                        style={{
                          fontSize: 13,
                          fontWeight: isSelected ? 600 : 400,
                          color: isSelected ? '#1890ff' : '#262626',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                        title={group.label}
                      >
                        {group.label}
                      </span>
                    </div>
                    <Badge
                      count={group.count}
                      style={{
                        backgroundColor: isSelected ? '#1890ff' : '#d9d9d9',
                        color: isSelected ? '#fff' : '#595959',
                        fontSize: 11,
                      }}
                      overflowCount={999}
                      showZero
                    />
                  </div>

                  {/* 二级分组 - 树状结构 */}
                  {hasChildren && isExpanded && (
                    <div
                      style={{
                        marginLeft: 20,
                        borderLeft: '1px solid #e0e0e0',
                        marginTop: 2,
                        marginBottom: 2,
                      }}
                    >
                      {group.children!.map((child, index) => {
                        const isChildSelected = selectedKey === child.key
                        const isLast = index === group.children!.length - 1

                        return (
                          <div
                            key={child.key}
                            onClick={() => onSelect(child.key)}
                            style={{
                              padding: '5px 12px 5px 16px',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              background: isChildSelected ? '#e6f4ff' : 'transparent',
                              position: 'relative',
                            }}
                          >
                            {/* 树状连接线 */}
                            <div
                              style={{
                                position: 'absolute',
                                left: 0,
                                top: '50%',
                                width: 12,
                                height: 1,
                                background: '#e0e0e0',
                              }}
                            />
                            <div style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0 }}>
                              <FolderOutlined style={{ fontSize: 12, color: '#8c8c8c', marginRight: 6, flexShrink: 0 }} />
                              <span
                                style={{
                                  fontSize: 12,
                                  fontWeight: isChildSelected ? 600 : 400,
                                  color: isChildSelected ? '#1890ff' : '#595959',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap',
                                }}
                                title={child.label}
                              >
                                {child.label}
                              </span>
                            </div>
                            <Badge
                              count={child.count}
                              style={{
                                backgroundColor: isChildSelected ? '#1890ff' : '#d9d9d9',
                                color: isChildSelected ? '#fff' : '#595959',
                                fontSize: 10,
                                flexShrink: 0,
                              }}
                              overflowCount={999}
                              showZero
                            />
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </>
        )}
      </div>
    </div>
  )
}

export default ResourceSidebar
