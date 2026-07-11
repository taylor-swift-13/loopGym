// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/hola/37.c

extern int unknown1();
extern int unknown2();

void loopy_137(int n) {
  int x= 0;
  int m=0;
  
  while(x<n) {
     if(unknown2()) {
	m = x;
     }
     x= x+1;
  }
  if(n>0) {;
//@ assert(0<=m && m<n);
}

}