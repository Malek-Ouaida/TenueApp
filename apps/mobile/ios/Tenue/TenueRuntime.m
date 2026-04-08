#import <React/RCTBridgeModule.h>
#import <TargetConditionals.h>

@interface TenueRuntime : NSObject <RCTBridgeModule>
@end

@implementation TenueRuntime

RCT_EXPORT_MODULE();

+ (BOOL)requiresMainQueueSetup
{
  return NO;
}

- (NSDictionary *)constantsToExport
{
  return @{
    @"isSimulator": @(TARGET_OS_SIMULATOR),
  };
}

@end
