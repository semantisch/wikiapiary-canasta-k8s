<?php
/**
 * Created by  : Open CSP.
 * Project     : WikiApiary
 * Filename    : Stats.php
 * Description :
 * Date        : 14-1-2024
 * Time        : 21:11
 */

namespace WikiApiary\data\query;

use MediaWiki\MediaWikiServices;
use WikiApiary\data\Structure;
use WikiApiary\data\Utils;
use Wikimedia\Rdbms\DBConnRef;

class Stats {
	private const CACHE_TTL = 3600;
	private const SNAPSHOT_PATH = __DIR__ . '/stats-snapshot.json';

	/**
	 * @var Structure
	 */
	private Structure $structure;

	public function __construct() {
		$this->structure = new Structure();
	}

	/**
	 * @param int $limit
	 * @param DBConnRef $dbr
	 * @param string $where
	 *
	 * @return array
	 */
	private function getMediaWikiVersionInfo( int $limit, DBConnRef $dbr, string $where = '' ): array {
		$select = [ Structure::SCRAPE_MEDIAWIKI_VERSION,
			'count' => 'count(*)' ];
		$from = Structure::DBTABLE_SCRAPE;
		try {
			if ( $where === '' ) {
				$res = $dbr->newSelectQueryBuilder()->
				select( $select )->
				from( $from )->
				groupBy( Structure::SCRAPE_MEDIAWIKI_VERSION )->
				orderBy( 'count', 'DESC' )->
				limit( $limit )->caller( __METHOD__ )->
				fetchResultSet();
			} else {
				$res = $dbr->newSelectQueryBuilder()->
				select( $select )->
				from( $from )->
				where( $where )->
				groupBy( Structure::SCRAPE_MEDIAWIKI_VERSION )->
				orderBy( 'count', 'DESC' )->
				limit( $limit )->
				caller( __METHOD__ )->
				fetchResultSet();
			}
		} catch ( \Exception $e ) {
			wfDebug( $e->getMessage(), 'w8y' );
			return [];
		}
		$ret = [];
		$t = 0;
		if ( $res->numRows() > 0 ) {
			while ( $row = $res->fetchRow() ) {
				$ret[$t]['Count'] = $row['count'];
				$ret[$t]['version'] = $row[ Structure::SCRAPE_MEDIAWIKI_VERSION ];
				$t++;
			}
		}

		return $ret;
	}

	/**
	 * @param int $limit
	 * @param DBConnRef $dbr
	 * @param string $where
	 *
	 * @return array
	 */
	private function getTopSkins( int $limit, DBConnRef $dbr, string $where = '' ): array {
		$select = [ Structure::SKIN_NAME, 'count' => 'count(*)' ];
		$from = Structure::DBTABLE_WIKIS;
		try {
			if ( $where !== '' ) {
				$res = $dbr->newSelectQueryBuilder()->
				select( $select )->
				from( $from )->
				leftJoin( Structure::DBTABLE_SCRAPE, null, Structure::DBTABLE_WIKIS . '.' . Structure::WIKI_LAST_SR_RCRD . '=' . Structure::DBTABLE_SCRAPE . '.' . Structure::SR_ID )->
				leftJoin( Structure::DBTABLE_SKINS_LINK, null, Structure::DBTABLE_SCRAPE . '.' . Structure::SCRAPE_VR_ID . '=' . Structure::DBTABLE_SKINS_LINK . '.' . Structure::SKIN_LINK_VID )->
				leftJoin( Structure::DBTABLE_SKINS, null, Structure::DBTABLE_SKINS_LINK . '.' . Structure::SKIN_LINK_ID . '=' . Structure::DBTABLE_SKINS . '.' . Structure::SKIN_ID )->
				where( $where )->
				groupBy( Structure::SKIN_NAME )->
				orderBy( 'count', 'DESC' )->
				limit( $limit )->
				caller( __METHOD__ )->
				fetchResultSet();
			} else {
				$res = $dbr->newSelectQueryBuilder()->
				select( $select )->
				from( $from )->
				leftJoin( Structure::DBTABLE_SCRAPE, null, Structure::DBTABLE_WIKIS . '.' . Structure::WIKI_LAST_SR_RCRD . '=' . Structure::DBTABLE_SCRAPE . '.' . Structure::SR_ID )->
				leftJoin( Structure::DBTABLE_SKINS_LINK, null, Structure::DBTABLE_SCRAPE . '.' . Structure::SCRAPE_VR_ID . '=' . Structure::DBTABLE_SKINS_LINK . '.' . Structure::SKIN_LINK_VID )->
				leftJoin( Structure::DBTABLE_SKINS, null, Structure::DBTABLE_SKINS_LINK . '.' . Structure::SKIN_LINK_ID . '=' . Structure::DBTABLE_SKINS . '.' . Structure::SKIN_ID )->
				groupBy( Structure::SKIN_NAME )->
				orderBy( 'count', 'DESC' )->
				limit( $limit )->
				caller( __METHOD__ )->
				fetchResultSet();
			}
		} catch ( \Exception $e ) {
			wfDebug( $e->getMessage(), 'w8y' );
			return [];
		}
		$ret = [];
		$t = 0;
		if ( $res->numRows() > 0 ) {
			while ( $row = $res->fetchRow() ) {
				$ret[$t]['Count'] = $row['count'];
				$ret[$t]['Name'] = $row[Structure::SKIN_NAME];
				$t++;
			}
		}

		return $ret;
	}

	/**
	 * @param int $limit
	 * @param DBConnRef $dbr
	 * @param string $where
	 *
	 * @return array
	 */
	private function getTopExtensions( int $limit, DBConnRef $dbr, string $where = '' ): array {
		$select = [ Structure::EXTENSION_NAME, 'count' => 'count(*)' ];
		$from = Structure::DBTABLE_WIKIS;
		try {
			if ( $where !== '' ) {
				$res = $dbr->newSelectQueryBuilder()->
				select( $select )->
				from( $from )->
				leftJoin( Structure::DBTABLE_SCRAPE, null, Structure::DBTABLE_WIKIS . '.' . Structure::WIKI_LAST_SR_RCRD . '=' . Structure::DBTABLE_SCRAPE . '.' . Structure::SR_ID )->
				leftJoin( Structure::DBTABLE_EXTENSIONS_LINK, null, Structure::DBTABLE_SCRAPE . '.' . Structure::SCRAPE_VR_ID . '=' . Structure::DBTABLE_EXTENSIONS_LINK . '.' . Structure::EXTENSION_LINK_VID )->
				leftJoin( Structure::DBTABLE_EXTENSIONS, null, Structure::DBTABLE_EXTENSIONS_LINK . '.' . Structure::EXTENSION_LINK_ID . '=' . Structure::DBTABLE_EXTENSIONS . '.' . Structure::EXTENSION_ID )->
				where( $where )->
				groupBy( Structure::EXTENSION_NAME )->
				orderBy( 'count', 'DESC' )->
				limit( $limit )->
				caller( __METHOD__ )->
				fetchResultSet();
			} else {
				$res = $dbr->newSelectQueryBuilder()->
				select( $select )->
				from( $from )->leftJoin( Structure::DBTABLE_SCRAPE, null, Structure::DBTABLE_WIKIS . '.' . Structure::WIKI_LAST_SR_RCRD . '=' . Structure::DBTABLE_SCRAPE . '.' . Structure::SR_ID )->
				leftJoin( Structure::DBTABLE_EXTENSIONS_LINK, null, Structure::DBTABLE_SCRAPE . '.' . Structure::SCRAPE_VR_ID . '=' . Structure::DBTABLE_EXTENSIONS_LINK . '.' . Structure::EXTENSION_LINK_VID )->
				leftJoin( Structure::DBTABLE_EXTENSIONS, null, Structure::DBTABLE_EXTENSIONS_LINK . '.' . Structure::EXTENSION_LINK_ID . '=' . Structure::DBTABLE_EXTENSIONS . '.' . Structure::EXTENSION_ID )->
				groupBy( Structure::EXTENSION_NAME )->
				orderBy( 'count', 'DESC' )->
				limit( $limit )->
				caller( __METHOD__ )->
				fetchResultSet();
			}
		} catch ( \Exception $e ) {
			wfDebug( $e->getMessage(), 'w8y' );
			return [];
		}
		$ret = [];
		$t = 0;
		if ( $res->numRows() > 0 ) {
			while ( $row = $res->fetchRow() ) {
				$ret[$t]['Count'] = $row['count'];
				$ret[$t]['Name'] = $row[Structure::EXTENSION_NAME];
				$t++;
			}
		}

		return $ret;
	}

	private function getSnapshotResults( string $action, string $where, int $limit ): ?array {
		if ( $where !== '' || !is_file( self::SNAPSHOT_PATH ) ) {
			return null;
		}

		$json = file_get_contents( self::SNAPSHOT_PATH );
		if ( $json === false ) {
			return null;
		}

		$data = json_decode( $json, true );
		if ( !is_array( $data ) || !isset( $data[$action] ) || !is_array( $data[$action] ) ) {
			return null;
		}

		return array_slice( $data[$action], 0, $limit );
	}

	/**
	 * @param string $action
	 * @param string $where
	 * @param int $limit
	 * @param string $export
	 *
	 * @return mixed
	 */
	public function doQuery( string $action, string $where, int $limit = 10, string $export = "table" ): mixed {
		$result = $this->getSnapshotResults( $action, $where, $limit );

		if ( $result === null ) {
			$cache = MediaWikiServices::getInstance()->getMainWANObjectCache();
			$cacheKey = $cache->makeKey(
				'wikiapiary',
				'stats',
				$action,
				sha1( $where ),
				$limit
			);

			$result = $cache->getWithSetCallback(
				$cacheKey,
				self::CACHE_TTL,
				function () use ( $action, $where, $limit ) {
					$lb = MediaWikiServices::getInstance()->getDBLoadBalancer();
					$dbr = $lb->getConnectionRef( DB_REPLICA );

					return match ( $action ) {
						'extensions' => $this->getTopExtensions( $limit, $dbr, $where ),
						'skins' => $this->getTopSkins( $limit, $dbr, $where ),
						'mwversion' => $this->getMediaWikiVersionInfo( $limit, $dbr, $where ),
						default => [],
					};
				}
			);
		}

		$tables = [ Structure::w8yMessage( 'w8y_count' ) ];
		switch ( $export ) {
			case "table":
				if ( $action === "extensions" ) {
					return Utils::renderTable( $result,
						'Top ' . $limit . ' used extensions',
						array_merge( $tables, [ Structure::w8yMessage( Structure::EXTENSION_NAME ) ] ),
						true );
				}
				if ( $action === "skins" ) {
					return Utils::renderTable( $result,
						'Top ' . $limit . ' used skins',
						array_merge( $tables, [ Structure::w8yMessage( Structure::SKIN_NAME ) ] ),
						true );
				}
				if ( $action === "mwversion" ) {
					return Utils::renderTable( $result,
						'Top ' . $limit . ' most used MediaWiki versions',
						array_merge( $tables, [ Structure::w8yMessage( Structure::SCRAPE_MEDIAWIKI_VERSION ) ] ),
						true );
				}
				break;
			case "arrayfunctions":
				return [ Utils::exportArrayFunction( $result ), 'nowiki' => true ];
			case "lua":
			case "json":
				return $result;
			default:
				return "";
		}
		return "";
	}
}
