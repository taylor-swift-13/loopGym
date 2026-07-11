// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/hola/41.c

extern int unknown1();

void loopy_140(int n, int flag) {
   
   

   if(n>=0){
   int k = 1;
   if(flag) {
	k = unknown1();
	if(k>=0) ; else return;
   }
   int i = 0, j = 0;
   while(i <= n) {
     i++;
     j+=i;
   }
   int z = k + i + j;
   {;
//@ assert(z > 2*n);
}

   }
   return;
}
